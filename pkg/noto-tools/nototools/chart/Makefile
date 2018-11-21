all: chart.pdf

CHART_FONTS = `cat LIST`

chart.pdf chart.ps: chart.py LIST
	@echo "Generating $@"
	@python $< $@ $(CHART_FONTS)
