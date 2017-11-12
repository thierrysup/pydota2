# NOTE: This code is to a large degree based on DeepMind work for 
#       AI in StarCraft2, just ported towards the Dota 2 game.
#       DeepMind's License is posted below.

"""A Dota 2 environment."""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from absl import logging

from pydota2.env import environment
from pydota2.lib import features
from pydota2.lib import run_parallel
from pydota2.lib import stopwatch


sw = stopwatch.sw

"""
THIS FILE IS NOT COMPLETE AND WILL NOT COMPILE CURRENTLY
"""

_possible_results = {
    "Victory": 1,
    "Defeat": -1,
}

difficulties = {
    "1": "Easy"
}

teams = {
    "Radiant": 2,
    "Dire": 3,
}

class Dota2Env(environment.Base):
    """
    A Dota 2 environment.
    The implementation details of the action and observation specs are in
    lib/features.py
    """

    def __init__(self, # pylint: disable=invalid-name
                _only_use_kwargs=None,
                difficulty=None,
                **kwargs):
        # pylint: disable=g-doc-args
        """
        Create a Dota 2 Env
        Args:
          _only_use_kwargs: Don't pass args, only kwargs.
          discount: Returned as part of the observation.
          visualize: Whether to pop up a window showing the camera and feature
                     layers. This won't work without access to a window manager.
          difficulty: One of 1-9,A. How strong should the bot be?
          step_mul: How many game steps per agent step (action/observation). None
                means use the map default.
          game_steps_per_episode: Game steps per episode, independent of the
                              step_mul. 0 means no limit. None means use the map default.
          score_index: -1 means use the win/loss reward, >=0 is the index into the
                   score_cumulative with 0 being the curriculum score. None means use
                   the map default.
          score_multiplier: How much to multiply the score by. Useful for negating.

        Raises:
          ValueError: if the difficulty is invalid.
        """
        # pylint: enable=g-doc-args
        if _only_use_kwargs:
            raise ValueError("All arguments must be passed as keyword arguments.")

        difficulty = difficulty and str(difficulty) or "1"
        if difficulty not in difficulties:
            raise ValueError("Bad difficulty")

        self._num_players = 5

        self._setup((difficulty), **kwargs)

    def _setup(self,
               player_setup,
               discount=1.0,
               visualize=False,
               p_controller=None,
               c_controller=None,
               team='Radiant',
               step_mul=None,
               game_steps_per_episode=None):
        
        self._discount = discount
        self._step_mul = step_mul
        self._total_steps = 0

        self._last_score = None
        self._episode_length = game_steps_per_episode
        self._episode_steps = 0

        self._p_controller = p_controller
        self._c_controller = c_controller
        self._parallel = run_parallel.RunParallel()  # Needed for multiplayer

        self._features = features.Features()
        
        if visualize:
            print("Rendering Requested but NOT IMPLEMENTED!!!")

        self._episode_count = 0
        self._obs = None
        self._state = environment.StepType.LAST # Want to jump to `reset`.
        logging.info("Environment is ready.")
        
    def observation_spec(self):
        """Look at Features for full specs."""
        return self._features.observation_spec()

    def action_spec(self):
        """Look at Features for full specs."""
        return self._features.action_spec()

    def _restart(self):
        raise Exception("dota2 env _restart() not implemented")

    @sw.decorate
    def reset(self):
        """Start a new episode."""
        self._episode_steps = 0
        if self._episode_count:
              # No need to restart for the first episode.
              self._restart()

        self._episode_count += 1
        logging.info("Starting episode: %s", self._episode_count)

        self._last_score = [0] * self._num_players
        self._state = environment.StepType.FIRST
        return self._step() 

    @sw.decorate
    def step(self, actions):
        """Apply actions, step the world forward, return observations."""
        if self._state == environment.StepType.LAST:
            return self.reset()

        # send each agent action to the dota2 client bot(s)
        self._parallel.run(
            (c.add_to_post_queue, self._features.transform_action(o.observation, a))
            for c, o, a in zip(self._c_controller, self._obs, actions)
        )

        self._state = environment.StepType.MID
        return self._step()

    def _step(self):
        self._obs = self._p_controller.get_from_proto_queue()
        
        # TODO(tewalds): How should we handle more than 2 agents and the case where
        # the episode can end early for some agents?
        outcome = [0] * self._num_players
        discount = self._discount
        
        print("Game State: %d" % (self._obs.game_state))
        if self._obs.game_state == 5:  # Episode over.
            self._state = environment.StepType.LAST
            discount = 0
    
        # TODO - lots to fill out
        if self._state == environment.StepType.LAST:
            logging.info("Episode finished. Outcome: %s, Reward: %s, Score: %s",
                         outcome, reward, [o["score_cumulative"][0] for o in agent_obs])

        return tuple(environment.TimeStep(step_type=self._state,
                     reward=r * self._score_multiplier,
                     discount=discount, observation=o)
                     for r, o in zip(reward, agent_obs))

    @property
    def state(self):
        return self._state

    def close(self):
        logging.info("Environment Close")

        self._p_controller.quit()
        self._c_controller.quit()

        logging.info(sw)
