"""Interface regulation of supporting different clusters

Author: Qianzhen (QZ) Shao <qianzhen.shao@vanderbilt.edu>
Date: 2022-04-13
"""
from abc import ABC, abstractmethod
from subprocess import CompletedProcess

class ClusterInterface(ABC):
    '''
    Defines the interface of a cluster
    ----------
    SUBMIT_CMD: the command for job submission
    
    '''
    ### class attribute ###
    @property
    @abstractmethod
    def SUBMIT_CMD(self) -> str:
        pass

    ### classmethods ###
    @classmethod
    @abstractmethod
    def format_submit_cmd(cls, sub_script_path: str) -> str:
        pass

    @classmethod
    @abstractmethod
    def format_resource_str(cls, res_dict: dict) -> str:
        pass

    @classmethod
    @abstractmethod
    def get_job_id_from_submit(cls, submit_job: CompletedProcess) -> str:
        pass