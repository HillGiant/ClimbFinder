FROM python:2.7-alpine
LABEL MAINTAINER mathew.luebbert@gmail.com

# Install climb-finder Python dependencies.
RUN \
    pip install beautifulsoup4; \
	pip install python-dateutil
	
COPY . /climb-finder

# Define entrypoint.
WORKDIR /climb-finder
ENTRYPOINT ["python", "-u", "ClimbFinder.py"]
CMD ["foo@example.com", "password"]
