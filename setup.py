
from setuptools import setup, find_packages

setup(
    name='pdf_analyzer',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[],
    entry_points={
        'console_scripts': [
            'pdf-analyzer=pdf_analyzer.cli:main'
        ]
    }
)
