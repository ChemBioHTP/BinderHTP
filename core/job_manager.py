"""Manage the job queue for running jobs on a cluster. Interface with different linux resource managers (e.g. slurm)
The general workflow is
    (take job commands)
    1) compile the submission script 
    2) submit and monitor the job 
    3) record the completion of the job.
    (give files containing the stdout/stderr)
In a dataflow point of view it should be analogous to subprocess.run()

Feature:
    - Allow users to add support for their own clusters. (By making new ClusterInterface classes)

Author: Qianzhen (QZ) Shao <qianzhen.shao@vanderbilt.edu>
Date: 2022-04-13
"""
import time
from typing import Union
from plum import dispatch
import os

from .clusters import *  # pylint: disable=unused-wildcard-import,wildcard-import
from core.clusters._interface import ClusterInterface
from helper import line_feed
from Class_Conf import Config


class ClusterJob():
    '''
    This class handle jobs for cluster calculation
    API:
    constructor:
        ClusterJob.config_job()
    property:
        cluster:    cluster used for running the job (pick from list in /core/cluster/)
        sub_script_str: submission script content
        sub_script_path: submission script path
    method:
        submit()
    '''

    def __init__(self, cluster: ClusterInterface, sub_script_str: str) -> None:
        self.cluster = cluster
        self.sub_script_str = sub_script_str

        self.sub_script_path: str = None
        self.sub_dir: str = None
        self.job_cluster_log: str = None
        self.job_id: str = None
        self.state: tuple = None # state and the update time in s

    ### config (construct object) ###
    @classmethod
    def config_job( cls, 
                commands: Union[list[str], str],
                cluster: ClusterInterface,
                env_settings: Union[list[str], str],
                res_keywords: dict[str, str]
                ) -> 'ClusterJob':
        '''
        config job and generate a ClusterJob instance (cluster, sub_script_str)

        Args:
        commands: 
            commands to run. Can be a str of commands or a list containing strings of commands.
        cluster: 
            cluster for running the job. Should be a ClusterInterface object. 
            Available clusters can be found under core/clusters as python class defination.
            To define a new cluster class for support, reference the ClusterInterface requirement.
        env_settings: 
            environment settings in the submission script. Can be a string or list of strings
            for cmds in each line.
            Since environment settings are attached to job types. It is more conserved than the command.
            **Use presets in ClusterInterface classes to save effort**
        res_keywords: 
            resource settings. Can be a dictionary indicating each keywords or the string of the whole section.
            The name and value should be exactly the same as required by the cluster.
            **Use presets in ClusterInterface classes to save effort**
        
        Return:
        A ClusterJob object

        Example:
        >>> cluster = accre.Accre()
        >>> job = ClusterJob.config_job(
                        commands = 'g16 < xxx.gjf > xxx.out',
                        cluster = cluster,
                        env_settings = [cluster.AMBER_GPU_ENV, cluster.G16_CPU_ENV],
                        res_keywords = cluster.CPU_RES
                    )
        >>> print(job.sub_script_str)    
        #!/bin/bash
        #SBATCH --core_type=cpu
        #SBATCH --node_cores=24
        #SBATCH --job_name=job_name
        #SBATCH --partition=production
        #SBATCH --mem_per_core=4G
        #SBATCH --walltime=24:00:00
        #SBATCH --account=xxx

        #Script generated by EnzyHTP in 2022-04-21 14:09:18

        export AMBERHOME=/dors/csb/apps/amber19/
        export CUDA_HOME=$AMBERHOME/cuda/10.0.130
        export LD_LIBRARY_PATH=$AMBERHOME/cuda/10.0.130/lib64:$AMBERHOME/cuda/RHEL7/10.0.130/lib:$LD_LIBRARY_PATH
        module load Gaussian/16.B.01
        mkdir $TMPDIR/$SLURM_JOB_ID
        export GAUSS_SCRDIR=$TMPDIR/$SLURM_JOB_ID

        g16 < xxx.gjf > xxx.out
        '''
        command_str = cls._get_command_str(commands)
        env_str = cls._get_env_str(env_settings)
        res_str = cls._get_res_str(res_keywords, cluster)
        sub_script_str = cls._get_sub_script_str(
                            command_str, 
                            env_str, 
                            res_str, 
                            f'# {Config.WATERMARK}{line_feed}'
                            )

        return cls(cluster, sub_script_str)

    @staticmethod
    @dispatch
    def _get_command_str(cmd: list) -> str:
        return line_feed.join(cmd) + line_feed

    @staticmethod
    @dispatch
    def _get_command_str(cmd: str) -> str:
        return cmd + line_feed

    @staticmethod
    @dispatch
    def _get_env_str(env: list) -> str:
        return line_feed.join(env) + line_feed

    @staticmethod
    @dispatch
    def _get_env_str(env: str) -> str:
        return env + line_feed

    @staticmethod
    @dispatch
    def _get_res_str(res: dict, cluster: ClusterInterface) -> str:
        return cluster.format_resource_str(res)

    @staticmethod
    @dispatch
    def _get_res_str(res: str, cluster: ClusterInterface) -> str:
        return res

    @staticmethod
    def _get_sub_script_str(command_str: str, env_str: str, res_str: str, watermark: str) -> str:
        '''
        combine command_str, env_str, res_str to sub_script_str
        '''
        sub_script_str = line_feed.join((res_str, watermark, env_str, command_str))
        return sub_script_str

    ### submit ###
    def submit(self, sub_dir, script_path=None, debug=0):
        '''
        submit the job to the cluster queue. Make the submission script. Submit.
        Arg:
            sub_dir: dir for submission. commands in the sub script usually run under this dir. 
            script_path: path for submission script generation. '
                         (default: sub_dir/submit.cmd; 
                          will be sub_dir/submit_#.cmd if the file exists
                          # is a growing index)
                         
        Return:
            self.job_id

        Attribute added:
            sub_script_path
            job_id
            sub_dir
        
        Example:
            >>> sub_dir = '/EnzyHTP-test/test_job_manager/'
            >>> job.submit( sub_dir= sub_dir,
                            script_path= sub_dir + 'test.cmd')
        '''
        # make default value for filename
        if script_path is None:
            script_path = sub_dir + '/submit.cmd'
            i = 0
            while os.path.isfile(script_path):
                i += 1
                script_path = sub_dir + f'/submit_{i}.cmd'  # TODO(shaoqz): move to helper

        self.sub_script_path = self._deploy_sub_script(script_path)
        self.job_id, self.job_cluster_log = self.cluster.submit_job(sub_dir, script_path, debug=debug)
        self.sub_dir = sub_dir

        return self.job_id

    def _deploy_sub_script(self, out_path: str) -> None:
        '''
        deploy the submission scirpt for current job
        store the out_path to self.sub_script_path
        '''
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(self.sub_script_str)
        return out_path

    ### control ###
    def kill(self):
        '''
        kill the job with the job_id
        '''
        self.require_job_id()

        if Config.debug >= 1:
            print(f'killing: {self.job_id}')
        self.cluster.kill_job(self.job_id)

    def hold(self):
        '''
        hold the job from running
        '''
        self.require_job_id()

        if Config.debug >= 1:
            print(f'holding: {self.job_id}')
        self.cluster.hold_job(self.job_id)

    def release(self):
        '''
        release the job to run
        '''
        self.require_job_id()

        if Config.debug >= 1:
            print(f'releasing: {self.job_id}')
        self.cluster.release_job(self.job_id)

    ### monitor ###
    def get_state(self) -> tuple[str, str]:
        '''
        determine if the job is:
        pend, 
        run, 
        complete, 
        canel,
        error

        Return: 
            a tuple of
            (a str of pend or run or complete or canel or error,
                the real keyword form the cluster)
        '''
        self.require_job_id()

        result = self.cluster.get_job_state(self.job_id)
        self.state = (result, time.time())
        return result

    def ifcomplete(self) -> bool:
        '''
        determine if the job is complete.
        '''
        return self.get_state()[0] == 'complete'

    def wait_to_end(self, period: int) -> None:
        '''
        monitor the job in a specified frequency
        until it ends with 
        complete, error, or cancel

        Args:
            period: the time cycle for each job state change (Unit: s)
        '''
        # san check
        self.require_job_id()
        # monitor job
        while True:
            # exit if job ended
            if self.get_state()[0] in ('complete', 'error', 'cancel'):
                return self._action_end_with(self.state[0])
            # check every {period} second 
            time.sleep(period)

    def _action_end_with(self, end_state: str) -> None:
        '''
        the action when job ends with the {end_state}
        the end_state can only be one of ('complete', 'error', 'cancel')
        '''
        general_state = end_state[0]
        detailed_state = end_state[1]

        if general_state not in ('complete', 'error', 'cancel'):
            raise TypeError("_action_end_with: only take state in ('complete', 'error', 'cancel')")
        # general action
        if Config.debug > 0:
            print(f'Job {self.job_id} end with {general_state}::{detailed_state} !')
        # state related action
        if general_state is 'complete':
            pass
        if general_state is 'error':
            pass
        if general_state is 'cancel':
            pass # may be support pass in callable to do like resubmit

    ### misc ###
    def require_job_id(self) -> None:
        '''
        require job to be submitted and have an id
        '''
        if self.job_id is None:
            raise AttributeError('Need to submit the job and get an job id!')
    
    @dispatch
    def _(self):
        '''
        dummy method for dispatch
        '''
        pass