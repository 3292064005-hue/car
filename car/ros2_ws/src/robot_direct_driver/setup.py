from setuptools import find_packages, setup

package_name = 'robot_direct_driver'

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
    description='Dedicated direct-driver lane package for inspection robot command/state authority.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'direct_driver_node = robot_direct_driver.direct_driver_node:main',
        ],
    },
)
