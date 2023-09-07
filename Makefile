default: help
help:
	@echo "Please use \`make <target>' where <target> is one of:"
	@echo "  help             to show this message"
	@echo "  lint             to run code linting"

lint:
	yamllint -f parsable tasks 
	ansible-lint -v --offline tasks/*
#	flake8 --ignore=E402,W503 --max-line-length=160 library
