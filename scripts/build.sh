#!/bin/bash	

cp -r ../blenderneuron blenderneuron	
docker build -t blenderneuron:latest .
rm -rf blenderneuron

