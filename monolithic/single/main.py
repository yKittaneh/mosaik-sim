import logging
import random

import mosaik
from mosaik.util import connect_randomly, connect_many_to_one

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
        'python': 'mosaik_pypower.mosaik:PyPower',
        # 'cmd': 'mosaik-pypower %(addr)s',
    },
    'WebVis': {
        'cmd': 'mosaik-web -s 0.0.0.0:8000 %(addr)s',
    },
    'NodeSimulator': {
        # 'connect': '0.0.0.0:8080',
        'connect': '127.0.0.1:5679',
    },
}

START = '2014-01-01 00:00:00'
END = 31 * 24 * 3600  # 1 day
PV_DATA = 'data/pv_10kw.csv'
PROFILE_FILE = 'data/profiles.data-single.gz'
# PROFILE_FILE = 'data/profiles.data-full.gz'
GRID_NAME = 'demo_lv_grid'
GRID_FILE = '%s.json' % GRID_NAME


def main():
    logger.info("Starting demo ...")
    random.seed(23)
    world = mosaik.World(sim_config)
    create_scenario(world)
    logger.info("Running world ...")
    # world.run(until=END)  # As fast as possilbe
    world.run(until=END, rt_factor=1 / 6000)  # Real_time_factor -- 1/60 means 1 simulation minute = 1 wall-clock second


def create_scenario(world):
    # Start simulatorscount=5
    logger.info("Creating scenario ...")
    pypower = world.start('PyPower', step_size=15 * 60)
    pvsim = world.start('CSV', sim_start=START, datafile=PV_DATA)
    node_simulator = world.start('NodeSimulator', sim_start=START, eid='edgeNode', grid_name=GRID_NAME,
                                 profile_file=PROFILE_FILE)

    # Instantiate models
    logger.info("Instantiating models ...")
    grid = pypower.Grid(gridfile=GRID_FILE).children

    pvs = pvsim.PV.create(1)

    edge_nodes = node_simulator.Node.create(num=1)

    logger.info("node_simulator_nodes =")
    logger.info(edge_nodes)

    # Connect entities
    logger.info("Connecting entities ...")
    buses = get_buses(grid)
    connect_randomly(world, pvs, [e for e in grid if 'node' in e.eid], 'P')

    # Connect edge node to grid
    connect_node_to_grid(world, edge_nodes, buses)
    # Connect edge node to PV
    connect_node_to_pv(world, edge_nodes, pvs)
    # connect_randomly(world, pvs, edge_nodes, ('P', 'pv_power'))

    # Database
    logger.info("Creating database ...")
    db = world.start('DB', step_size=60, duration=END)
    hdf5 = db.Database(filename='demo.hdf5')
    connect_many_to_one(world, pvs, hdf5, 'P')
    connect_many_to_one(world, edge_nodes, hdf5, 'P_out')

    nodes = [e for e in grid if e.type in ('RefBus, PQBus')]
    connect_many_to_one(world, nodes, hdf5, 'P', 'Q', 'Vl', 'Vm', 'Va')

    branches = [e for e in grid if e.type in ('Transformer', 'Branch')]
    connect_many_to_one(world, branches, hdf5,
                        'P_from', 'Q_from', 'P_to', 'P_from')

    # Web visualization
    logger.info("Creating web visualization ...")
    webvis = world.start('WebVis', start_date=START, step_size=60)
    webvis.set_config(ignore_types=['Topology', 'ResidentialLoads', 'Grid',
                                    'Database'])
    vis_topo = webvis.Topology()

    logger.info("Connecting entities to web visualization ...")
    connect_many_to_one(world, nodes, vis_topo, 'P', 'Vm')
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

    connect_many_to_one(world, pvs, vis_topo, 'P')
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

    connect_many_to_one(world, edge_nodes, vis_topo, 'P_out')
    webvis.set_etypes({
        'Node': {
            'cls': 'load',
            'attr': 'P_out',
            'unit': 'P [W]',
            'default': 0,
            'min': 0,
            'max': 5000,
        },
    })


def connect_buildings_to_grid(world, houses, buses):
    house_data = world.get_data(houses, 'node_id')
    for house in houses:
        node_id = house_data[house]['node_id']
        world.connect(house, buses[node_id], ('P_out', 'P'))


def connect_node_to_grid(world, nodes, buses):
    logger.info("***** inside connect_node_to_grid")
    node_data = world.get_data(nodes, 'grid_node_id')
    for node in nodes:
        grid_node_id = node_data[node]['grid_node_id']
        world.connect(node, buses[grid_node_id], ('P_out', 'P'))
        # todo (medium/high): the below connection seems wrong. I think P should not feed into grid_power because edgeNode.P_out feeds into gridNode.P, as seen in the above world.connect line. Need to figure out what P is.
        world.connect(buses[grid_node_id], node, ('P', 'grid_power'), time_shifted=True, initial_data={'P': 0})


def connect_node_to_pv(world, edge_nodes, pvs):
    logger.info("***** inside connect_node_to_pv")
    for node in edge_nodes:
        random.choice(pvs)
        world.connect(random.choice(pvs), node, ('P', 'pv_power'))


def get_buses(grid):
    buses = filter(lambda e: e.type == 'PQBus', grid)
    buses = {b.eid.split('-')[1]: b for b in buses}
    return buses


if __name__ == '__main__':
    main()
