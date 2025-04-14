from setuptools import find_packages, setup

package_name = 'turtle_agentros2'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='sako.r.chekerjian@jpl.nasa.gov',
    description='Embodied ROSA agent for the TurtleSim robot. ROS 2 Version',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'talker = turtle_agentros2.turtle_agent:main',
        ],
    },
)
