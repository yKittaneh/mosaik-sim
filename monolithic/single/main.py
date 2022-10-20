import logging
import random

import mosaik
from mosaik.util import connect_many_to_one

logging.basicConfig()
logger = logging.getLogger('demo')
logger.setLevel(logging.INFO)

sim_config = {
    'CSV': {
        'python': 'mosaik_csv:CSV',
    },
    'DB': {
        'cmd': 'mosaik-hdf5 %(addr)s',
    },
    'PyPower': {
        # 'python': 'mosaik_pypower.mosaik:PyPower',
        # 'cmd': 'mosaik-pypower %(addr)s',
        'connect': '127.0.0.1:5677',
    },
    'WebVis': {
        'cmd': 'mosaik-web -s 0.0.0.0:8000 %(addr)s',
    },
    # 'NodeSimulator': {
    #     # 'connect': '0.0.0.0:8080',
    #     'connect': '127.0.0.1:5679',
    # },
    'BatterySimulator': {
        # 'connect': '0.0.0.0:8080',
        'connect': '127.0.0.1:5678',
    },
    'ComputeNodeSimulator': {
        # 'connect': '0.0.0.0:8080',
        'connect': '127.0.0.1:5676',
    },
}

START = '2014-01-01 00:00:00'
END = 31 * 24 * 3600  # 1 day
PV_DATA = 'data/pv_10kw.csv'
PROFILE_FILE = 'data/profiles.data-single.gz'
# PROFILE_FILE = 'data/profiles.data-full.gz'
GRID_NAME = 'demo_lv_grid'
GRID_FILE = '%s.json' % GRID_NAME
IS_BATTERY_SIMULATED = True


def main():
    logger.info("Starting demo ...")
    random.seed(23)
    world = mosaik.World(sim_config)
    create_scenario(world)
    logger.info("Running world ...")
    # world.run(until=END)  # As fast as possilbe
    world.run(until=END, rt_factor=1 / 60)  # Real_time_factor -- 1/60 means 1 simulation minute = 1 wall-clock second


def create_scenario(world):
    # Start simulatorscount=5
    logger.info("Creating scenario ...")
    pypower = world.start('PyPower', step_size=15 * 60)
    pvsim = world.start('CSV', sim_start=START, datafile=PV_DATA)
    # node_simulator = world.start('NodeSimulator', sim_start=START, eid='edgeNode', grid_name=GRID_NAME,
    #                              profile_file=PROFILE_FILE, is_battery_simulated=IS_BATTERY_SIMULATED)
    battery_simulator = world.start('BatterySimulator', sim_start=START, eid='batteryNode', profile_resolution=15)
    compute_simulator = world.start('ComputeNodeSimulator', eid='computeNode')

    # ######## Instantiate models
    logger.info("Instantiating models ...")

    # pyPower
    grid = pypower.Grid(gridfile=GRID_FILE).children
    buses = get_buses(grid)
    grid_node = buses['node_a1']

    # pv
    pv_nodes = pvsim.PV.create(1)

    # compute
    compute_nodes = compute_simulator.ComputeNode.create(1)

    # edge
    # edge_nodes = node_simulator.Node.create(num=1)

    # battery
    battery_nodes = battery_simulator.Battery.create(1, grid_node_id='0-node_a1')

    # logger.info("node_simulator_nodes =")
    # logger.info(edge_nodes)

    # ######## Connect entities
    logger.info("Connecting entities ...")

    # compute node to grid node
    connect_compute_node_to_grid(world, compute_nodes[0], grid_node)

    # todo: edge node not needed anymore, make sure this is correct!! it is correct. Remove it
    # edge node to compute node
    # connect_edge_node_to_compute_node(world, edge_nodes[0], compute_nodes[0])
    # Connect edge node to PV
    # connect_edge_node_to_pv(world, edge_nodes, pv_nodes)
    # connect_randomly(world, pv_nodes, edge_nodes, ('P', 'pv_power'))

    # PV connections
    connect_pv_to_compute_node(world, pv_nodes[0], compute_nodes[0])
    connect_pv_to_grid(world, pv_nodes[0], grid_node)
    # connect_randomly(world, pv_nodes, [e for e in grid if 'node' in e.eid], 'P')

    # Battery connections
    connect_battery_to_compute_node(world, battery_nodes[0], compute_nodes[0])
    connect_battery_to_grid(world, battery_nodes[0], grid_node)
    # edge_grid_node_id = get_grid_node_id(world, edge_nodes)
    # connect_battery_to_pv(world, battery_nodes[0], pv_nodes[0])
    # connect_battery_to_edge_node(world, battery_nodes[0], edge_nodes[0])

    ##############
    # world.connect(edge_nodes[0], battery_nodes[0], ('test', 'test'))
    ##############

    # ######## Database # todo add net metering from pypower to db
    logger.info("Creating database ...")
    db = world.start('DB', step_size=60, duration=END)
    hdf5 = db.Database(filename='demo.hdf5')
    connect_many_to_one(world, pv_nodes, hdf5, 'P')

    # todo: what data to save from the compute node?
    connect_many_to_one(world, compute_nodes, hdf5, 'container_need')

    # connect_many_to_one(world, edge_nodes, hdf5, 'P_out')
    connect_many_to_one(world, battery_nodes, hdf5, 'current_load')

    grid_nodes = [e for e in grid if e.type in ('RefBus', 'PQBus')]
    connect_many_to_one(world, grid_nodes, hdf5, 'P', 'Q', 'Vl', 'Vm', 'Va')

    grid_branches = [e for e in grid if e.type in ('Transformer', 'Branch')]
    connect_many_to_one(world, grid_branches, hdf5,'P_from', 'Q_from', 'P_to', 'P_from')

    # ######## Web visualization
    logger.info("Creating web visualization ...")
    webvis = world.start('WebVis', start_date=START, step_size=60)
    webvis.set_config(ignore_types=['Topology', 'ResidentialLoads', 'Grid', 'Database'])
    vis_topo = webvis.Topology()

    logger.info("Connecting entities to web visualization ...")
    connect_many_to_one(world, grid_nodes, vis_topo, 'P', 'Vm')
    webvis.set_etypes({
        'RefBus': {
            'cls': 'refbus',
            'attr': 'P',
            'unit': 'P [W]',
            'default': 0,
            'min': 0,
            'max': 30000,
        },
        'PQBus': {
            'cls': 'pqbus',
            'attr': 'Vm',
            'unit': 'U [V]',
            'default': 230,
            'min': 0.99 * 230,
            'max': 1.01 * 230,
        },
    })

    connect_many_to_one(world, compute_nodes, vis_topo, 'container_need')
    webvis.set_etypes({
        'ComputeNode': {
            'cls': 'compute',
            'attr': 'container_need',
            'unit': 'P [W]',
            'default': 0,
            'min': -10000,
            'max': 10000,
        },
    })

    connect_many_to_one(world, pv_nodes, vis_topo, 'P')
    webvis.set_etypes({
        'PV': {
            'cls': 'gen',
            'attr': 'P',
            'unit': 'P [W]',
            'default': 0,
            'min': -10000,
            'max': 0,
        },
    })

    # todo: should battery power be in the minus always?
    #  just like PVs, this is provided power unlike houses/container, where P is positive meaning how much power they take/require
    connect_many_to_one(world, battery_nodes, vis_topo, 'current_load')
    webvis.set_etypes({
        'Battery': {
            'cls': 'battery',
            'attr': 'current_load',
            'unit': 'P [W]',
            'default': 0,
            'min': -50000,
            'max': 50000,
        },
    })


def connect_buildings_to_grid(world, houses, buses):
    house_data = world.get_data(houses, 'node_id')
    for house in houses:
        node_id = house_data[house]['node_id']
        world.connect(house, buses[node_id], ('P_out', 'P'))


def connect_compute_node_to_grid(world, compute_node, grid_node):
    logger.info("***** inside connect_compute_node_to_grid")
    world.connect(compute_node, grid_node, 'container_need')


# def connect_edge_node_to_compute_node(world, edge_node, compute_node):
#     logger.info("***** inside connect_edge_node_to_compute_node")
#     world.connect(edge_node, compute_node, ('P_out', 'edge_node_need'))


# def connect_edge_node_to_pv(world, edge_nodes, pv_node):
#     logger.info("***** inside connect_edge_node_to_pv")
#     for node in edge_nodes:
#         random.choice(pv_node)
#         world.connect(random.choice(pv_node), node, ('P', 'pv_power'))


def connect_battery_to_compute_node(world, battery, compute_node):
    logger.info("***** inside connect_battery_to_compute_node")
    # world.connect(grid_node, battery, ('excess_pv_power', 'charge'))
    # world.connect(battery, grid_node, ('current_load', 'temp'), weak=True, initial_data={'current_load': 0})
    world.connect(battery, compute_node, ('current_load', 'battery_power'))
    # world.connect(grid_node, battery, ('battery_action', 'battery_action'), weak=True, initial_data={'battery_action': 'initial_message'})
    # todo: need the below line? telling the battery to charge or discharge  by the compute node, most likely yes
    # world.connect(compute_node, battery, 'battery_action', time_shifted=True, initial_data={'battery_action': 'charge:0'})


def connect_battery_to_grid(world, battery, grid_node):
    logger.info("***** inside connect_battery_to_grid")
    world.connect(battery, grid_node, ('current_load', 'P'))
    world.connect(grid_node, battery, 'battery_action', time_shifted=True, initial_data={'battery_action': 'charge:0'})


def connect_pv_to_compute_node(world, pv, compute_node):
    logger.info("***** inside connect_pv_to_compute_node")
    world.connect(pv, compute_node, ('P', 'pv_power'))


def connect_pv_to_grid(world, pv, grid_node):
    logger.info("***** inside connect_pv_to_grid")
    world.connect(pv, grid_node, 'P')


def get_buses(grid):
    buses = filter(lambda e: e.type == 'PQBus', grid)
    buses = {b.eid.split('-')[1]: b for b in buses}
    return buses


# def get_grid_node_id(world, edge_nodes):
#     logger.info("***** inside get_grid_node_id")
#     node_data = world.get_data(edge_nodes, 'grid_node_id')
#     return node_data[edge_nodes[0]]['grid_node_id']


if __name__ == '__main__':
    main()
