from setuptools import find_packages, setup

package_name = 'robot_nav2_adapter'

setup(
    name=package_name,
    version='0.2.0',
    packages=find_packages(include=[package_name, f'{package_name}.*']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'PyYAML>=6.0'],
    zip_safe=True,
    maintainer='Inspection Robot Maintainers',
    maintainer_email='maintainers@inspection-robot.invalid',
    description='Separate experimental navigation adapter lane for provider switching.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'nav2_adapter_node = robot_nav2_adapter.nav2_adapter_node:main',
        ],
    },
)
