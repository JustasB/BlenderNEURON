#!/bin/bash	

cp -r ../blenderneuron blenderneuron	
docker build -t blenderneuron:2.0.0 .	
rm -rf blenderneuron

