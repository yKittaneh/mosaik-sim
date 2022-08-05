import logging
import random

from mosaik.util import connect_randomly, connect_many_to_one
import mosaik

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
    'HouseholdSim': {
        'python': 'householdsim.mosaik:HouseholdSim',
        # 'cmd': 'mosaik-householdsim %(addr)s',
    },
    'PyPower': {
        'python': 'mosaik_pypower.mosaik:PyPower',
        # 'cmd': 'mosaik-pypower %(addr)s',
    },
    'WebVis': {
        'cmd': 'mosaik-web -s 0.0.0.0:8000 %(addr)s',
    },
}

START = '2014-01-01 00:00:00'
END = 31 * 24 * 3600  # 1 day
PV_DATA = 'data/pv_10kw.csv'
PROFILE_FILE = 'data/profiles.data.gz'
GRID_NAME = 'demo_lv_grid'
GRID_FILE = '%s.json' % GRID_NAME


def main():
    logger.info("Starting demo ...")
    random.seed(23)
    world = mosaik.World(sim_config)
    create_scenario(world)
    logger.info("Running world ...")
    world.run(until=END)  # As fast as possilbe
    # world.run(until=END, rt_factor=1/60)  # Real-time 1min -> 1sec


def create_scenario(world):
    # Start simulatorscount=5
    logger.info("Creating scenario ...")
    pypower = world.start('PyPower', step_size=15*60)
    hhsim = world.start('HouseholdSim')
    pvsim = world.start('CSV', sim_start=START, datafile=PV_DATA)

    # Instantiate models
    logger.info("Instantiating models ...")
    grid = pypower.Grid(gridfile=GRID_FILE).children
    houses = hhsim.ResidentialLoads(sim_start=START,
                                    profile_file=PROFILE_FILE,
                                    grid_name=GRID_NAME).children
    pvs = pvsim.PV.create(20)

    # leaf = world.start('LEAF', data_file=PROFILE_FILE, step_size=15 * 60)
    # leaf_nodes = leaf.EdgeNode.create(num=3, init_value='1')

    # Connect entities
    logger.info("Connecting entities ...")
    buses = get_buses(grid)
    connect_buildings_to_grid(world, houses, buses)
    connect_randomly(world, pvs, [e for e in grid if 'node' in e.eid], 'P')

    # Connect leafNodes to PVs on grid
    # connect_leaf_nodes_to_grid(world, leaf_nodes, buses)

    # Database
    logger.info("Creating database ...")
    db = world.start('DB', step_size=60, duration=END)
    hdf5 = db.Database(filename='demo.hdf5')
    connect_many_to_one(world, houses, hdf5, 'P_out')
    connect_many_to_one(world, pvs, hdf5, 'P')
    # connect_many_to_one(world, leaf_nodes, hdf5, 'P_out')

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

    connect_many_to_one(world, houses, vis_topo, 'P_out')
    webvis.set_etypes({
        'House': {
            'cls': 'load',
            'attr': 'P_out',
            'unit': 'P [W]',
            'default': 0,
            'min': 0,
            'max': 3000,
        },
    })

    # connect_many_to_one(world, leaf_nodes, vis_topo, 'P_out')
    # webvis.set_etypes({
    #     'Nodes': {
    #         'cls': 'load',
    #         'attr': 'P_out',
    #         'unit': 'P [W]',
    #         'default': 0,
    #         'min': 0,
    #         'max': 3000,
    #     },
    # })

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


def connect_buildings_to_grid(world, houses, buses):
    house_data = world.get_data(houses, 'node_id')
    for house in houses:
        node_id = house_data[house]['node_id']
        world.connect(house, buses[node_id], ('P_out', 'P'))


def connect_leaf_nodes_to_grid(world, leaf_nodes, buses):
    node_data = world.get_data(leaf_nodes, 'node_id')
    for node in leaf_nodes:
        node_id = node_data[node]['node_id']
        #node_id = node.node_id
        world.connect(node, buses[node_id], ('P_out', 'P'))

    pass


def get_buses(grid):
    buses = filter(lambda e: e.type == 'PQBus', grid)
    buses = {b.eid.split('-')[1]: b for b in buses}
    return buses


if __name__ == '__main__':
    main()
