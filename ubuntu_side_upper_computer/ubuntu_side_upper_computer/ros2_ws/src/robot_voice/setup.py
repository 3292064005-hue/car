from setuptools import setup

package_name = 'robot_voice'

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
    description='Voice command filtering and speech queue.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'voice_node = robot_voice.voice_node:main',
        ],
    },
)
