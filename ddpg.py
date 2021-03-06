import torch
import torch.nn.functional as F
import torch.optim as optim
import numpy as np

from model import Actor, Critic
from buffer import ReplayBuffer
from OUNoise import OUNoise

TAU = 1e-3
LR_ACTOR = 1e-4
LR_CRITIC = 5e-4

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

class DDPGAgent:
	def __init__(self, state_size, action_size, random_seed):
		
		self.state_size = state_size
		self.action_size = action_size
		self.seed = random_seed
		
		# ------------------ actor ------------------ #
		self.actor_local = Actor(state_size, action_size, random_seed).to(device)
		self.actor_target = Actor(state_size, action_size, random_seed).to(device)
		
		# ------------------ critic ----------------- #
		self.critic_local = Critic(state_size, action_size, random_seed).to(device)
		self.critic_target = Critic(state_size, action_size, random_seed).to(device)
		
		# ------------------ optimizers ------------- #
		self.actor_optimizer = optim.Adam(self.actor_local.parameters(), lr=LR_ACTOR)
		self.critic_optimizer = optim.Adam(self.critic_local.parameters(), lr=LR_CRITIC)

		# ----------------------- initialize target networks ----------------------- #
		self.soft_update(self.critic_local, self.critic_target, 1)
		self.soft_update(self.actor_local, self.actor_target, 1)

		# Noise process
		self.noise = OUNoise(action_size, random_seed)

	def act(self, state, add_noise=True):
		"""Returns actions for given state as per current policy."""
		state = torch.from_numpy(state).float().to(device)
		self.actor_local.eval()
		with torch.no_grad():
			action = self.actor_local(state).cpu().data.numpy()
		self.actor_local.train()
		
		if add_noise:
			action += self.noise.sample()
		return np.clip(action, -1, 1)

	def reset(self):
		self.noise.reset()

	def learn(self, experiences, gamma):
	
		states, actions, rewards, next_states, dones = experiences

		# ---------------------------- update critic ---------------------------- #
		# Get predicted next-state actions and Q values from target models
		actions_next = self.actor_target(next_states)
		Q_targets_next = self.critic_target(next_states, actions_next)
		# Compute Q targets for current states (y_i)
		Q_targets = rewards + (gamma * Q_targets_next * (1 - dones))
		# Compute critic loss
		Q_expected = self.critic_local(states, actions)
		critic_loss = F.mse_loss(Q_expected, Q_targets)
		# Minimize the loss
		self.critic_optimizer.zero_grad()
		critic_loss.backward()
		torch.nn.utils.clip_grad_norm_(self.critic_local.parameters(), 1)
		self.critic_optimizer.step()

		# ---------------------------- update actor ---------------------------- #
		# Compute actor loss
		actions_pred = self.actor_local(states)
		actor_loss = -self.critic_local(states, actions_pred).mean()
		# Minimize the loss
		self.actor_optimizer.zero_grad()
		actor_loss.backward()
		self.actor_optimizer.step()

		# ----------------------- update target networks ----------------------- #
		self.soft_update(self.critic_local, self.critic_target, TAU)
		self.soft_update(self.actor_local, self.actor_target, TAU)
		
	def soft_update(self, local_model, target_model, tau):
		"""Soft update model parameters.
		θ_target = τ*θ_local + (1 - τ)*θ_target

		Params
		======
			local_model: PyTorch model (weights will be copied from)
			target_model: PyTorch model (weights will be copied to)
			tau (float): interpolation parameter 
		"""
		for target_param, local_param in zip(target_model.parameters(), local_model.parameters()):
			target_param.data.copy_(tau*local_param.data + (1.0-tau)*target_param.data)
