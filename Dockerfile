FROM python:3.7-buster

ENV AIRFLOW_USER_HOME=/airflow
ENV AIRFLOW_USER="airflow"
ENV AIRFLOW_UID="1000"
ENV AIRFLOW_GID="100"
ENV AIRFLOW_HOME=$AIRFLOW_USER_HOME

RUN apt update && apt install -y curl
RUN mkdir /build
RUN curl "https://repo.anaconda.com/archive/Anaconda3-2020.02-Linux-x86_64.sh" > /build/conda-install.sh
RUN bash /build/conda-install.sh -b -p /anaconda
RUN /anaconda/bin/conda install numpy ninja pyyaml mkl mkl-include setuptools cmake cffi typing
RUN pip3 install pyyaml numpy WTForms==2.2.1


RUN mkdir /airflow
RUN mkdir /src

RUN cd /src && git clone https://github.com/optimuspaul/airflow.git && cd /src/airflow && git checkout v1-10-stable && git pull origin v1-10-stable

RUN pip install psycopg2 retry click wildflower-honeycomb-sdk boto3

RUN useradd -ms /bin/bash -u $AIRFLOW_UID airflow && \
  chown $AIRFLOW_USER:$AIRFLOW_GID $AIRFLOW_USER_HOME && \
  buildDeps='freetds-dev libkrb5-dev libsasl2-dev libssl-dev libffi-dev libpq-dev' \
  apt-get install -yqq --no-install-recommends $buildDeps build-essential default-libmysqlclient-dev && \
  cd /src/airflow && pip install --no-cache-dir .[postgres,kubernetes,crypto,rabbitmq,slack,ssh,redis,docker] && \
  apt-get purge --auto-remove -yqq $buildDeps && \
  apt-get autoremove -yqq --purge && \
  rm -rf /var/lib/apt/lists/*

RUN sed -i 's/execution_date,/execution_date.isoformat(),/' /usr/local/lib/python3.7/site-packages/airflow/api/client/json_client.py

WORKDIR /airflow

COPY ./scripts/ /airflow/scripts/
