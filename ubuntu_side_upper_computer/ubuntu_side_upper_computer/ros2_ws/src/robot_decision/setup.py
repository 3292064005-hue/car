from setuptools import setup

package_name = 'robot_decision'

setup(
    name=package_name,
    version='0.2.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Inspection Robot Maintainers',
    maintainer_email='maintainers@inspection-robot.invalid',
    description='State machine, patrol and track orchestration.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'decision_node = robot_decision.decision_node:main',
        ],
    },
)
