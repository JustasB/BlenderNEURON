from setuptools import setup, find_packages

with open('README.txt') as file:
    long_description = file.read()

setup(name='blenderneuron',
      version='0.1.5',
      description='Interface for Blender <-> NEURON',
      long_description=long_description,
      author='Justas Birgiolas',
      author_email='justas@asu.edu',
      url='http://BlenderNEURON.org',
      packages=find_packages(),
      platforms=["Linux", "Mac OS", "Windows"],
      keywords=["Blender", "NEURON", "neuroscience", "visualization", "neural networks", "neurons", "3D"],
      license="MIT",
      install_requires=[],
      classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Topic :: Scientific/Engineering :: Visualization",
       ],
       test_suite="blenderneuron.tests.client",
 )
