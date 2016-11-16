######################
## Static Variables ##
######################
PY_VER := 2.7
VENV_PATH := venv

###
# Define helpers for checking if a variable is non-empty
###
check_defined = $(strip \
	$(foreach 1,$1, \
		$(call __check_defined,$1,$(strip $(value 2)))))
__check_defined = $(if \
	$(value $1),, \
	$(error Undefined $1$(if $2, ($2))$(if $(value @), required by target `$@')))

###
# Define a Perl-based help output generator
# Ref: https://gist.github.com/prwhite/8168133
###
HELP_FUNC = \
	%help; \
	while(<>) { \
		if(/^([a-z0-9_-]+)\s*:.*\#\#(?:@([^\s]+))?\s(.*)$$/) { \
			push(@{$$help{$$2}}, [$$1, $$3]); \
		} \
	}; \
	print "usage: make [target]\n\n"; \
	for ( sort keys %help ) { \
		print "$$_:\n"; \
		printf("  %-20s %s\n", $$_->[0], $$_->[1]) for @{$$help{$$_}}; \
		print "\n"; \
	}

#############
## Targets ##
#############
.PHONY : help
help   : ##@Targets Show this help menu
	@echo  $(MAKEFILE_LIST)
	@perl -e '$(HELP_FUNC)' $(MAKEFILE_LIST)

venv : ##@Targets Creates a virualenv for any project-level dependencies
	@virtualenv -p python$(PY_VER) $(VENV_PATH)

.PHONY : dev
dev    : venv ##@Targets Installs dependencies in a virtualenv
dev    : venv
	@$(VENV_PATH)/bin/pip install \
		--quiet \
		-e . \
		-e .[test]

.PHONY : clean
clean  : ##@Targets Removes build files & virtualenv
clean  :
	@rm -fr $(VENV_PATH)/
