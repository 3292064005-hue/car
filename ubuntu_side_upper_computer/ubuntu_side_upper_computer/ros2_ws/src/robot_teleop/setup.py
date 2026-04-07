from setuptools import setup

package_name = 'robot_teleop'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Inspection Robot Maintainers',
    maintainer_email='maintainers@inspection-robot.invalid',
    description='Keyboard teleop for inspection robot.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'keyboard_teleop = robot_teleop.keyboard_teleop:main',
        ],
    },
)
