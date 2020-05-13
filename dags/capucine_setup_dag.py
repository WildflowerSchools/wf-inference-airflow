# from datetime import datetime, timedelta
#
# from airflow import DAG
# from airflow.contrib.operators.kubernetes_pod_operator import KubernetesPodOperator
# from airflow.contrib.kubernetes.secret import Secret
# from airflow.contrib.kubernetes.volume import Volume
# from airflow.contrib.kubernetes.volume_mount import VolumeMount
# from airflow.operators.dummy_operator import DummyOperator
#
# from wftools.honeycomb import get_assignments, get_environment_id
#
# DATA_PROCESS_DIRECTORY = '/data/prepared'
# DURATION = '1d'
#
# default_args = {
#     'owner': 'root',
#     'depends_on_past': False,
#     'start_date': "2020-03-01",
#     'email': ['tech@wildflowerschools.org'],
#     'email_on_failure': False,
#     'email_on_retry': False,
#     'retries': 1,
#     'retry_delay': timedelta(minutes=1),
# }
#
# dag = DAG('capucine-setup', schedule_interval="@once", default_args=default_args, catchup=False)
#
#
# start = DummyOperator(
#     task_id='start',
#     dag=dag,
# )
#
#
# end = DummyOperator(
#     task_id='end',
#     dag=dag,
# )
#
#
# environment_id = get_environment_id('capucine')
# assignments = get_assignments(environment_id)
# results = []
# for assignment, device_id in assignments:
#     message = {
#         "assignment_id": assignment,
#         "device_id": device_id,
#     }
#     results.append(message)
#
# secret_all_keys  = Secret('env', None, 'airflow-env')
# volume_mount = VolumeMount('data-volume', mount_path='/data', sub_path=None, read_only=False)
# volume_config= {
#     'hostPath':
#       {
#         'path': '/data',
#         'type': 'Directory',
#       }
#     }
# volume = Volume(name='data-volume', configs=volume_config)
#
# preps = []
# poses = []
#
# for assignment in results:
#     prepare = KubernetesPodOperator(namespace='airflow',
#             name=f"capucine-{assignment['assignment_id']}-prepare-task",
#             task_id=f"capucine-{assignment['assignment_id']}-prepare-task",
#             image="wildflowerschools/wf-deep-docker:video-prepare-tooling-v26",
#             cmds=["python"],
#             arguments=[
#                 "-m",
#                 "inference_helpers",
#                 "prepare-assignment-videos",
#                 "--environment_name",
#                 "capucine",
#                 "--start",
#                 "{{ ts[:-3] + ts[-2:] }}",
#                 "--duration",
#                 DURATION,
#                 "--assignment",
#                 assignment['assignment_id'],
#                 "--device",
#                 assignment['device_id'],
#             ],
#             env_vars={'DATA_ROOT': '/data/metadata', 'DATA_PROCESS_DIRECTORY': DATA_PROCESS_DIRECTORY},
#             secrets=[secret_all_keys],
#             volumes=[volume],
#             volume_mounts=[volume_mount],
#             is_delete_operator_pod=False,
#             dag=dag,
#             get_logs=True,
#         )
#
#     alphapose = KubernetesPodOperator(namespace='airflow',
#             name=f"capucine-{assignment['assignment_id']}-alphapose-task",
#             task_id=f"capucine-{assignment['assignment_id']}-alphapose-task",
#             image="wildflowerschools/wf-deep-docker:alphapose-producer-v29",
#             cmds=["producer"],
#             arguments=[
#                 "poses",
#                 environment_id,
#                 assignment['assignment_id'],
#                 "{{ ts[:-3] + ts[-2:] }}",
#                 DURATION,
#             ],
#             pool='GPU',
#             env_vars={'GPUS': '0,1', 'ENABLE_POSEFLOW': 'no', 'ENV': 'production', 'DATA_ROOT': '/data/metadata', 'DATA_PROCESS_DIRECTORY': DATA_PROCESS_DIRECTORY},
#             secrets=[secret_all_keys],
#             volumes=[volume],
#             volume_mounts=[volume_mount],
#             is_delete_operator_pod=False,
#             resources={'limit_gpu': 1},
#             dag=dag,
#             get_logs=True,
#         )
#
#     upload = KubernetesPodOperator(namespace='airflow',
#             name=f"capucine-{assignment['assignment_id']}-upload-task",
#             task_id=f"capucine-{assignment['assignment_id']}-upload-task",
#             image="wildflowerschools/wf-deep-docker:alphapose-producer-v29",
#             cmds=["producer"],
#             arguments=[
#                 "upload-poses",
#                 environment_id,
#                 assignment['assignment_id'],
#                 "{{ ts[:-3] + ts[-2:] }}",
#                 DURATION,
#             ],
#             pool='default_pool',
#             env_vars={'GPUS': '0,1', 'ALPHA_POSE_POSEFLOW': 'false', 'ENV': 'production', 'DATA_ROOT': '/data/metadata', 'DATA_PROCESS_DIRECTORY': DATA_PROCESS_DIRECTORY},
#             secrets=[secret_all_keys],
#             volumes=[volume],
#             volume_mounts=[volume_mount],
#             is_delete_operator_pod=False,
#             dag=dag,
#             get_logs=True,
#         )
#
#     prepare >> alphapose >> upload
#     preps.append(prepare)
#     poses.append(upload)
#
# start >> preps
# end.set_upstream(poses)
