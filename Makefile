AWS_REGION := $(shell aws configure get region)
AWS_ACCOUNT_ID := $(shell aws sts get-caller-identity --query 'Account' --output text)
SAGEMAKER_BUCKET := sagemaker-$(AWS_REGION)-$(AWS_ACCOUNT_ID)

install:
	@echo "Configuring AWS CodeArtifact for pip..."
	aws codeartifact login --tool pip --domain tba-investments --domain-owner $(AWS_ACCOUNT_ID) --repository tba-investments-etl --region $(AWS_REGION)
	@echo "Debugging pip configuration..."
	pip config list
	@echo "Attempting to install dependencies..."
	python -m pip install --upgrade pip &&\
		pip install -r requirements.txt --verbose --extra-index-url https://pypi.org/simple/ &&\
		pip install -r dev_requirements.txt --verbose --extra-index-url https://pypi.org/simple/ &&\
		pip install -r tests/test_requirements.txt --verbose --extra-index-url https://pypi.org/simple/ &&\
		pip install -e . --use-pep517 --verbose --extra-index-url https://pypi.org/simple/

update-conda-env:
	conda remove --name esg-env --all -y || true
	conda create --name esg-env python=3.9 -y
	conda init bash
	# You may need to run the following command manually in terminal
	conda activate esg-env
	make install

format:
	black mediasent tests
	isort mediasent tests

lint:
	pylint mediasent tests --rcfile=.pylintrc
	black --check --diff mediasent tests
	isort --check-only mediasent tests

test:
	python -m pytest -v

pre_pr: format lint test

upload-mediasent-code:
	aws s3 cp ./mediasent/preprocessing.py s3://$(SAGEMAKER_BUCKET)/mediasent/code/
	aws s3 cp ./mediasent/inference.py s3://$(SAGEMAKER_BUCKET)/mediasent/code/
	aws s3 cp ./mediasent/serve s3://$(SAGEMAKER_BUCKET)/mediasent/code/
	aws s3 cp ./mediasent/model_config.json s3://$(SAGEMAKER_BUCKET)/mediasent/config/
	aws s3 cp ./mediasent/prompt_template.txt s3://$(SAGEMAKER_BUCKET)/mediasent/config/

free-docker-memory:
	docker system prune -f
	docker image prune -a
	docker volume prune -f

push-mediasent-container:
	chmod +x ./mediasent/build_and_push.sh
	AWS_ACCOUNT_ID=$(AWS_ACCOUNT_ID) AWS_REGION=$(AWS_REGION) ./mediasent/build_and_push.sh

deploy-mediasent-pipeline:
	make upload-mediasent-code
	python ./mediasent/deploy_pipeline.py
