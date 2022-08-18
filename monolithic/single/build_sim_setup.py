import pathlib
import shutil
import re
import sys
from mosaik_docker._config import ORCH_CONTEXT_DIR_NAME, ORCH_CONTEXT_EXTRA_DIR_NAME, ORCH_IMAGE_NAME_TEMPLATE
from mosaik_docker.util.execute import execute_and_stream_output
from mosaik_docker.util.config_data import ConfigData


def build_sim_setup(setup_dir, out_stream=print):
    '''
    Build simulation setup as preparation for running the simulation.
    This includes building the Docker image of the mosaik orchestrator.

    :param setup_dir: path to simulation setup (string)
    :param out_stream: output from the build process to stderr will be piped to this stream (callable)
    :return: return dict with status of build process:
        {
            'valid': flag indicating if build succeded (boolean)
            'status': detailed status message (string)
        }
    '''

    if not callable(out_stream):
        raise TypeError('Parameter \'out_stream\' must be callable')

    # Retrieve simulation setup configuration.
    config_data = ConfigData(setup_dir)

    try:
        # Retrieve data from config file.
        sim_setup_id = config_data['id'].strip()
        config_data_orch = config_data['orchestrator']
        start_file = config_data_orch['start_file'].strip()  # <-- Yazan
        sim_jar = config_data_orch['sim_jar'].strip()  # <-- Yazan
        app_jar = config_data_orch['app_jar'].strip()  # <-- Yazan
        docker_file = config_data_orch['docker_file'].strip()
        extra_files = [f.strip() for f in config_data_orch['extra_files']]
        extra_dirs = [d.strip() for d in config_data_orch['extra_dirs']]

        # Check if scenario file and Dockerfile exists.
        start_file_path = pathlib.Path(setup_dir, start_file).resolve(strict=True)  # <-- Yazan
        sim_jar_path = pathlib.Path(setup_dir, sim_jar).resolve(strict=True)  # <-- Yazan
        app_jar_path = pathlib.Path(setup_dir, app_jar).resolve(strict=True)  # <-- Yazan
        docker_file_path = pathlib.Path(setup_dir, docker_file).resolve(strict=True)
        extra_file_paths = [pathlib.Path(setup_dir, f).resolve(strict=True) for f in extra_files]
        extra_dir_paths = [pathlib.Path(setup_dir, d).resolve(strict=True) for d in extra_dirs]

        # Define path for "context directory". All resources needed to create the orchestrator image will be copied there.
        orch_context_dir = pathlib.Path(setup_dir, ORCH_CONTEXT_DIR_NAME).resolve(strict=False)
        orch_context_extra_dir = pathlib.Path(orch_context_dir, ORCH_CONTEXT_EXTRA_DIR_NAME).resolve(strict=False)

        # Check if context directory already exists. If yes, delete it.
        if orch_context_dir.is_dir():
            shutil.rmtree(orch_context_dir)

        # Create new context directory.
        orch_context_dir.mkdir(exist_ok=False)
        orch_context_extra_dir.mkdir(exist_ok=False)

        # Copy resources to context directory.
        shutil.copy(start_file_path, orch_context_dir)  # <-- Yazan
        shutil.copy(sim_jar_path, orch_context_dir)  # <-- Yazan
        shutil.copy(app_jar_path, orch_context_dir)  # <-- Yazan
        for f in extra_file_paths:
            shutil.copy(f, orch_context_dir)
        for d in extra_dir_paths:
            shutil.copytree(d, pathlib.Path(orch_context_dir, d.name))

        # Define Docker image name.
        docker_image_name = ORCH_IMAGE_NAME_TEMPLATE.format(sim_setup_id.lower())

        cmd = [
            'docker', 'build',  # Docker build command.
            '-t', docker_image_name,  # Specify image name.
            '--build-arg', 'START_FILE={}'.format(start_file),  # <-- Yazan
            '--build-arg', 'SIM_JAR={}'.format(sim_jar),  # <-- Yazan
            '--build-arg', 'APP_JAR={}'.format(app_jar),  # <-- Yazan
            '--build-arg', 'EXTRA={}'.format(ORCH_CONTEXT_EXTRA_DIR_NAME),
            # Specify directory with extra files and directories.
            '-f', docker_file_path,  # Specify the Dockerfile.
            orch_context_dir  # Specify the build context.
        ]

        execute_and_stream_output(cmd, out_stream)

    except Exception as err:
        return dict(
            valid=False,
            status='building simulation setup failed:\n{}\nrun "check_sim_setup" for details'.format(err)
        )

    return dict(
        valid=True,
        status='building simulation setup succeeded: {}'.format(config_data.path.parent)
    )


def main():
    import argparse
    import sys

    # Command line parser.
    parser = argparse.ArgumentParser(
        description='Build simulation setup as preparation for running the simulation. This includes building the Docker image of the mosaik orchestrator.'
    )

    parser.add_argument(
        'setup_dir',
        nargs='?',
        default='.',
        metavar='SETUP_DIR',
        help='path to simulation setup directory (default: current working directory)'
    )

    args = parser.parse_args()

    try:
        build_status = build_sim_setup(args.setup_dir)

        print(build_status['status'])
        if True == build_status['valid']:
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as err:

        print(str(err))
        sys.exit(3)


if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(main())