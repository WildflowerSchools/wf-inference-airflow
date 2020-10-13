from datetime import datetime, timedelta
import os
import json

from airflow import DAG
from airflow.operators.docker_operator import DockerOperator
from airflow.contrib.kubernetes.secret import Secret
from airflow.contrib.kubernetes.volume import Volume
from airflow.contrib.kubernetes.volume_mount import VolumeMount
from airflow.operators.dummy_operator import DummyOperator
from airflow.utils.helpers import chain

from wftools.honeycomb import get_assignments, get_environment_id

DATA_PROCESS_DIRECTORY = '/data/prepared'
DURATION = '1h'

default_args = {
    'owner': 'root',
    'depends_on_past': False,
    'start_date': "2020-01-01",
    'email': ['tech@wildflowerschools.org'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

date_pattern = "{{ ts[:13] }}"

dag = DAG('capucine-setup-hourly-v0', schedule_interval="@once", default_args=default_args, catchup=False)

alpha_image = "wildflowerschools/wf-deep-docker:alphapose-producer-v87"

start = DummyOperator(
    task_id=f'start',
    dag=dag,
)


end = DummyOperator(
    task_id=f'end',
    dag=dag,
)


environment_id = get_environment_id('capucine')
assignments = get_assignments(environment_id)
results = []
for assignment, device_id in assignments:
    message = {
        "assignment_id": assignment,
        "device_id": device_id,
    }
    results.append(message)


with open(os.path.join(os.path.dirname(__file__), "secrets.json"), 'r') as secio:
    secrets = json.load(secio)

prepare_env = secrets.copy()
prepare_env.update({'DATA_ROOT': '/data/metadata', 'DATA_PROCESS_DIRECTORY': DATA_PROCESS_DIRECTORY})

alphapose_env = secrets.copy()
alphapose_env.update({'MAX_ATTEMPTS': '100', 'ALPHA_POSE_POSEFLOW': 'false', 'ENV': 'production', 'DATA_PROCESS_DIRECTORY': DATA_PROCESS_DIRECTORY})

upload_env = secrets.copy()
upload_env.update({'DATA_PROCESS_DIRECTORY': DATA_PROCESS_DIRECTORY})

preps = []
poses = []



timestamp_pattern = "{{ ts[:-3] + ts[-2:] }}"


for i, assignment in enumerate(results):
    prepare = DockerOperator(
            container_name=f"capucine-{assignment['assignment_id']}-{date_pattern}-prepare-task",
            task_id=f"capucine-{assignment['assignment_id']}-prepare-task",
            image="wildflowerschools/wf-deep-docker:video-prepare-tooling-v30",
            command=[
                "python",
                "-m",
                "inference_helpers",
                "prepare-assignment-videos",
                "--environment_name",
                "capucine",
                "--start",
                timestamp_pattern,
                "--duration",
                DURATION,
                "--assignment",
                assignment['assignment_id'],
                "--device",
                assignment['device_id'],
            ],
            execution_timeout=timedelta(hours=2),
            force_pull=False,
            environment=prepare_env,
            volumes=["/data:/data"],
            dag=dag,
            docker_url='unix://var/run/docker.sock',
            network_mode='host',
            api_version='auto',
            auto_remove=True,
        )
    previous = prepare
    for x in range(1,7):
        alpha = DockerOperator(
                container_name=f"capucine-{assignment['assignment_id']}-{date_pattern}-{x}-alphapose-task",
                task_id=f"capucine-{assignment['assignment_id']}-{x}-alphapose-task",
                image=alpha_image,
                command=[
                    "alphapose-runner",
                    "--verbose",
                    "--environment_id",
                    environment_id,
                    "--assignment_id",
                    assignment['assignment_id'],
                    "--start",
                    "{{ ts[:-3] + ts[-2:] }}",
                    "--dur",
                    DURATION,
                    "--slot",
                    str(x),
                ],
                execution_timeout=timedelta(hours=8),
                force_pull=False,
                pool=f'gpu',
                environment=alphapose_env,
                volumes=["/data:/data"],
                dag=dag,
                docker_url='unix://var/run/docker.sock',
                network_mode='host',
                api_version='auto',
                auto_remove=True,
                tty=True,
            )
        previous >> alpha
        previous = alpha
        # alpha = DummyOperator(
        #     task_id=f"capucine-{assignment['assignment_id']}-{x}-alphapose-task",
        #     dag=dag,
        # )
        uptask = DockerOperator(
                container_name=f"capucine-{assignment['assignment_id']}-{date_pattern}-{x}-upload-task",
                task_id=f"capucine-{assignment['assignment_id']}-{x}-upload-task",
                image=alpha_image,
                command=[
                    "producer",
                    "upload-poses",
                    environment_id,
                    assignment['assignment_id'],
                    "{{ ts[:-3] + ts[-2:] }}",
                    DURATION,
                    str(x),
                    "alphapose_coco18",
                ],
                execution_timeout=timedelta(hours=6),
                force_pull=False,
                pool='default_pool',
                environment=upload_env,
                volumes=["/data:/data"],
                dag=dag,
                docker_url='unix://var/run/docker.sock',
                network_mode='host',
                api_version='auto',
                auto_remove=True,
            )
        # uptask = DummyOperator(
        #     task_id=f"capucine-{assignment['assignment_id']}-{x}-upload-task",
        #     dag=dag,
        # )
        previous >> uptask
        previous = uptask
    completed = DummyOperator(
        task_id=f"capucine-{assignment['assignment_id']}-complete",
        dag=dag,
    )
    previous >> completed
    poses.append(completed)
    preps.append(prepare)

start >> preps
end << poses
