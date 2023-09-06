default: help
help:
	@echo "Please use \`make <target>' where <target> is one of:"
	@echo "  help             to show this message"
	@echo "  lint             to run code linting"

lint:
	yamllint -f parsable tasks 

