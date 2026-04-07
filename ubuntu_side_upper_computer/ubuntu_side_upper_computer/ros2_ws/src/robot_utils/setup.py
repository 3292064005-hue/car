from setuptools import setup

package_name = 'robot_utils'

setup(
    name=package_name,
    version='0.2.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'PyYAML>=6.0'],
    zip_safe=True,
    maintainer='Inspection Robot Maintainers',
    maintainer_email='maintainers@inspection-robot.invalid',
    description='Shared constants and helpers for the inspection robot.',
    license='MIT',
    tests_require=['pytest'],
)
