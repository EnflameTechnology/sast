FROM python:3.8-alpine


#### set repo and install basic library
RUN sed -i s/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g /etc/apk/repositories \
    && echo "http://mirrors.aliyun.com/alpine/latest-stable/main/" > /etc/apk/repositories \
    && echo "http://mirrors.aliyun.com/alpine/latest-stable/community/" >> /etc/apk/repositories \
    && apk update \
    && apk add --no-cache git wget readline-dev bash cloc file curl openssl \
    tzdata zlib zlib-dev git-lfs gojq sqlite-dev build-base libffi-dev \
    && apk cache clean \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

#### install jsonlint & markdownlint-cli2
RUN apk add --no-cache npm \
    && npm install markdownlint-cli2 --global

#### install cppcheck-2.7.4
RUN wget -P /tmp https://github.com/danmar/cppcheck/archive/refs/tags/2.7.4.tar.gz \
    && cd /tmp \
    && tar -xf 2.7.4.tar.gz  \
    && cd cppcheck-2.7.4/ \
    && apk add make g++ \
    && make install FILESDIR=/ \
    && cd /tmp \
    && rm -rf /tmp/* \
    && apk del make g++

#### install shellcheck-v0.8.0
RUN wget -qO- https://github.com/koalaman/shellcheck/releases/download/v0.8.0/shellcheck-v0.8.0.linux.x86_64.tar.xz | tar -xJf - \
    && cd shellcheck-v0.8.0/ \
    && cp shellcheck /usr/local/bin  \
    && cd ../ \
    && rm -rf shellcheck-v0.8.0/


#### install gitleaks
RUN wget -P /tmp https://github.com/gitleaks/gitleaks/releases/download/v8.27.2/gitleaks_8.27.2_linux_x64.tar.gz \
    && cd /tmp \
    && tar -xf gitleaks_8.27.2_linux_x64.tar.gz \
    && mv gitleaks /usr/local/bin \
    && rm -rf gitleaks_8.27.2_linux_x64.tar.gz

#### install ruff
RUN wget -P /tmp https://github.com/astral-sh/ruff/releases/download/0.6.4/ruff-x86_64-unknown-linux-gnu.tar.gz \
    && cd /tmp \
    && tar -xf ruff-x86_64-unknown-linux-gnu.tar.gz \
    && cd ruff-x86_64-unknown-linux-gnu/ \
    && cp ruff /usr/local/bin \
    && cd ../ \
    && rm -rf ruff-x86_64-unknown-linux-gnu/ ruff-x86_64-unknown-linux-gnu.tar.gz

RUN wget https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-x86_64 -O /usr/local/bin/hadolint \
    && chmod +x /usr/local/bin/hadolint

#### add project
COPY . /sast/

#### add module package
RUN python3.8 -m pip install --no-cache-dir -U -r /sast/requirements.txt

WORKDIR /app

RUN chmod -R 777 /app && chmod -R 777 /sast/

#### display port
EXPOSE 22

#### start ssh server
#CMD ["/usr/sbin/sshd", "-D"]