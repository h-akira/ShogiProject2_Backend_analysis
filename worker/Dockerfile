FROM public.ecr.aws/lambda/python:3.13

# Install build tools for YaneuraOu compilation
RUN dnf install -y gcc gcc-c++ make

WORKDIR /var/task

# Copy engine source and pre-configured files
COPY Engine Engine
COPY YaneuraOu YaneuraOu

# Compile YaneuraOu
WORKDIR /var/task/YaneuraOu/source
RUN make && mv YaneuraOu-by-gcc /var/task/Engine/

# Copy Lambda handler
WORKDIR /var/task
COPY handler.py ${LAMBDA_TASK_ROOT}
COPY engine.py ${LAMBDA_TASK_ROOT}

CMD [ "handler.handler" ]
