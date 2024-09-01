import yaml
import numpy as np


class Settings:

    def __init__(self, config_file='config.yaml'):
        with open(config_file) as f:
            self.config = config = yaml.safe_load(f)

        self.output_folder = config['output_folder']
        self.pre_foto_sleep = config['pre_foto_sleep']
        self.end_position = config['end_position']

        self.port = config['serial_settings']['port']
        self.baud_rate = config['serial_settings']['baud_rate']
