from setuptools import find_packages, setup

package_name = 'robot_bridge'

setup(
    name=package_name,
    version='0.2.0',
    packages=find_packages(include=[package_name, f'{package_name}.*']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Inspection Robot Maintainers',
    maintainer_email='maintainers@inspection-robot.invalid',
    description='TCP JSON bridge between ROS2 and ESP32 gateway.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'bridge_node = robot_bridge.bridge_node:main',
            'bridge_transport_node = robot_bridge.bridge_transport_node:main',
            'bridge_protocol_node = robot_bridge.bridge_protocol_node:main',
            'bridge_projection_node = robot_bridge.bridge_projection_node:main',
            'bridge_health_node = robot_bridge.bridge_health_node:main',
        ],
    },
)
