default: help
help:
	@echo "Please use \`make <target>' where <target> is one of:"
	@echo "  help             to show this message"
	@echo "  lint             to run code linting"

lint:
	yamllint -f parsable tasks 
	ansible-lint -v --offline tasks/*
#	find ./ -path venv -prune  -name "*.py" -exec flake8 --max-line-length=160 {} \;
