#!/bin/bash

export AIRFLOW_HOME=/airflow

airflow upgradedb

airflow connections -l | awk '{print $2}' | grep default | xargs -n 1 airflow connections -d --conn_id
airflow connections -d --conn_id azure_container_instances_default
airflow connections -d --conn_id airflow_db
airflow connections -d --conn_id local_mysql
