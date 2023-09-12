default: help
help:
	@echo "Please use \`make <target>' where <target> is one of:"
	@echo "  help             to show this message"
	@echo "  lint             to run code linting"

VENV_DIR := /tmp/venv_$(shell date +'%Y%m%d%H%M')

venv:
	python3 -m venv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate
	pip install flake8


.PHONY: venv

lint: venv
	yamllint -f parsable tasks 
	ansible-lint -v --offline tasks/*
	find ./ -name "*.py" -exec flake8 --max-line-length=160 {} \;
