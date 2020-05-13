.PHONY: build install destroy deploy proxy-admin

VERSION ?= 0

build:
	docker build -t wildflowerschools/wf-deep-docker:airflow-v$(VERSION) .
	docker push wildflowerschools/wf-deep-docker:airflow-v$(VERSION)

install:
	mkdir -p /data/airflow/dags
	cp -r dags/* /data/airflow/dags/

destroy:
	microk8s.kubectl delete -f deploy/
	rm -rf /data/airflow/airflow_db/*


deploy:
	microk8s.kubectl apply -f deploy/namespace.yml
	microk8s.kubectl apply -f deploy/config.yml
	microk8s.kubectl apply -f deploy/


proxy-admin:
	microk8s.kubectl -n airflow port-forward deployment/airflow-web 8088:8080
