from setuptools import setup, find_packages

setup(
    name="test-authoring-agent",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        # read from requirements.txt if desired
    ],
    entry_points={
        'console_scripts': [
            'test-agent=cli.main:cli',
        ],
    },
    python_requires='>=3.10',
)
