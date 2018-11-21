# Base image for noto repos, with required libraries

FROM python:2.7
COPY ./basesetup.sh /tmp
RUN /tmp/basesetup.sh
ENTRYPOINT ["/bin/bash"]
