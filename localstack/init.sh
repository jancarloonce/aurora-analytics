#!/bin/bash
set -e

awslocal kinesis create-stream \
  --stream-name news-api-stream \
  --shard-count 1

echo "Kinesis stream 'news-api-stream' created successfully"
