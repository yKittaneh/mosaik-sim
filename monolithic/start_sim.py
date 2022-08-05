import json
import re
import sys

from mosaik_docker._config import ORCH_IMAGE_NAME_TEMPLATE
from mosaik_docker.util.config_data import ConfigData
from mosaik_docker.util.create_unique_id import create_unique_id
from mosaik_docker.util.execute import execute


def start_sim(setup_dir, id=None):
    '''
    Start a new simulation.

    :param setup_dir: path to simulation setup (string)
    :param id: ID of new simulation (string, default: None)
    :return: on success, return new simulation ID (int)
    '''

    print('calling start_sim ...')

    if not id == None and not isinstance(id, str):
        raise TypeError('Parameter \'id\' must be of type \'str\'')

    if id == None:
        id = create_unique_id()

    # Retrieve simulation setup configuration.
    config_data = ConfigData(setup_dir)

    sim_setup_id = config_data['id'].strip()
    config_data_orch = config_data['orchestrator']
    scenario_file = config_data_orch['scenario_file'].strip()
    start_file = config_data_orch['start_file'].strip()
    spring_jar = config_data_orch['spring_jar'].strip()
    nodes_config_file = config_data_orch['nodes_config_file'].strip()

    sim_ids_up = config_data['sim_ids_up']
    sim_ids_down = config_data['sim_ids_down']

    if id in sim_ids_up or id in sim_ids_down:
        raise RuntimeError('Simulation ID \'{}\' has already been used'.format(id))

    # Define Docker image name.
    docker_image_name = ORCH_IMAGE_NAME_TEMPLATE.format(sim_setup_id.lower())

    command = [
        'docker', 'run',  # Docker run command.
        '--detach',  # Run container in background.
        # '--rm', # Only for debugging.
        # '-it',  # Only for debugging.
        '--name', id,  # Specify container name as simulation id.
        '--env', 'SCENARIO_FILE={}'.format(scenario_file),  # Specify scenario file.
        '--env', 'START_FILE={}'.format(start_file),  # Specify shell start file. <-- Yazan
        '--env', 'SPRING_JAR={}'.format(spring_jar),  # <-- Yazan
        '--env', 'NODES_CONFIG_FILE={}'.format(nodes_config_file),  # <-- Yazan
        '--net', 'mosaik-net',  # Specify docker network to connect to <-- Yazan # todo: is it needed? given that everything is run in one docker for now. If still needed then make it configurable in mosaik-docker.json
        '-p', '8000:8000',  # Specify port forwarding <-- Yazan
    ]

    with open(nodes_config_file) as f:
        json_dict = json.load(f)
        print('json config file: ' + json.dumps(json_dict, indent = 4))
        for i in json_dict['workerNodes']:
            command.append('-p')
            command.append(i['port'] + ':' + i['port'])

    command.append(docker_image_name)  # Specify the Docker image.

    print('going to execute command: ' + command.__str__())
    print(command.__str__())

    execute(command)

    # Update sim setup config.
    sim_ids_up.append(id)

    # Save simulation setup configuration.
    config_data.write()

    # On success, return new simulation ID.
    return id


def main():
    import argparse
    import sys

    # Command line parser.
    parser = argparse.ArgumentParser(
        description='Start a new simulation.'
    )

    parser.add_argument(
        'setup_dir',
        nargs='?',
        default='.',
        metavar='SETUP_DIR',
        help='path to simulation setup directory (default: current working directory)'
    )

    parser.add_argument(
        'id',
        nargs='?',
        default=None,
        metavar='ID',
        help='simulation ID (Docker container name)'
    )

    args = parser.parse_args()

    try:
        sim_id = start_sim(args.setup_dir, args.id)

        print('Started new simulation with ID = {}'.format(sim_id))
        sys.exit(0)

    except Exception as err:

        print(str(err))
        sys.exit(3)


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(main())
