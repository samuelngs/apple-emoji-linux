# Build image for noto repos.

FROM toolbase:latest
COPY *.sh /tmp/
RUN /tmp/notosetup.sh
RUN /tmp/initfccache.sh
ENTRYPOINT ["/bin/bash"]
