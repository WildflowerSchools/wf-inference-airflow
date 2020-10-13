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
DURATION = '1d'

prepare_image = "wildflowerschools/wf-deep-docker:video-prepare-tooling-v30"
open_pose_image = "wildflowerschools/wf-deep-docker:cuda10.2-openpose-base-v6"
upload_image = "wildflowerschools/wf-deep-docker:alphapose-producer-v69"

default_args = {
    'owner': 'root',
    'depends_on_past': False,
    'start_date': "2020-03-10",
    'email': ['tech@wildflowerschools.org'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

dag = DAG('capucine-openpose-setup-v0', schedule_interval="@once", default_args=default_args, catchup=False)


start = DummyOperator(
    task_id='start',
    dag=dag,
)


end = DummyOperator(
    task_id='end',
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

openpose_env_0 = secrets.copy()
openpose_env_0.update({'MODEL_NAME': 'BODY_25', 'GPU': '0', 'MAX_ATTEMPTS': '100', 'ENV': 'production', 'DATA_ROOT': '/data/metadata', 'DATA_PROCESS_DIRECTORY': DATA_PROCESS_DIRECTORY})
openpose_env_1 = openpose_env_0.copy()
openpose_env_1['GPU'] = 1

upload_env = secrets.copy()
upload_env.update({'DATA_ROOT': '/data/metadata', 'DATA_PROCESS_DIRECTORY': DATA_PROCESS_DIRECTORY, 'MODEL_NAME': 'BODY_25'})

preps = []
poses = []

timestamp_pattern = "{{ ts[:-3] + ts[-2:] }}"

for i, assignment in enumerate(results):
    prepare = DockerOperator(
            container_name=f"capucine-{assignment['assignment_id']}-prepare-task",
            task_id=f"capucine-{assignment['assignment_id']}-prepare-task",
            image=prepare_image,
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
            execution_timeout=timedelta(hours=4),
            force_pull=False,
            environment=prepare_env,
            volumes=["/data:/data"],
            dag=dag,
            docker_url='unix://var/run/docker.sock',
            network_mode='bridge',
            api_version='auto',
            auto_remove=True,
        )
    gpu = i % 2
    open_pose = DockerOperator(
            container_name=f"capucine-{assignment['assignment_id']}-openpose-task",
            task_id=f"capucine-{assignment['assignment_id']}-openpose-task",
            image=open_pose_image,
            command=[
                "openpose_runner",
                "--verbose",
                "--environment_id",
                environment_id,
                "--assignment_id",
                assignment['assignment_id'],
                "--date",
                "{{ ts[:4] }}/{{ ts[5:7] }}/{{ ts[8:10] }}",
                "--num_gpu",
                "1",
                "--num_gpu_start",
                str(gpu),
            ],
            execution_timeout=timedelta(hours=8),
            force_pull=False,
            pool=f'gpu_{gpu}',
            environment=openpose_env_0 if gpu == 0 else openpose_env_1,
            volumes=["/data:/data"],
            dag=dag,
            docker_url='unix://var/run/docker.sock',
            network_mode='bridge',
            api_version='auto',
            auto_remove=True,
        )
    prepare >> open_pose
    previous = open_pose
    for x in range(1,7):
        uptask = DockerOperator(
                container_name=f"capucine-{assignment['assignment_id']}-{x}-upload-task",
                task_id=f"capucine-{assignment['assignment_id']}-{x}-upload-task",
                image=upload_image,
                command=[
                    "producer",
                    "upload-poses",
                    environment_id,
                    assignment['assignment_id'],
                    "{{ ts[:-3] + ts[-2:] }}",
                    DURATION,
                    str(x),
                   "openpose_body_25",
                ],
                execution_timeout=timedelta(hours=6),
                force_pull=False,
                pool='default_pool',
                environment=upload_env,
                volumes=["/data:/data"],
                dag=dag,
                docker_url='unix://var/run/docker.sock',
                network_mode='bridge',
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
