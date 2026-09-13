document.querySelectorAll('.tab-button').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

    button.classList.add('active');
    document.getElementById(`tab-${button.dataset.tab}`).classList.add('active');
  });
});


fetch('http://localhost:8000/episodes')
  .then(response => response.json())
  .then(episodes => {
    const list = document.getElementById('episode-list');
    for (const episode of episodes) {
      const item = document.createElement('li');
      item.textContent = `${episode.title} — ${episode.status} (${episode.target_minutes} min)`;
      list.appendChild(item);
    }
  })
  .catch(error => {
    document.getElementById('error').textContent = 'Error: ' + error;
  });

  
fetch('http://localhost:8000/agents')
  .then(response => response.json())
  .then(agents => {
    const checkboxContainer = document.getElementById('agent-checkboxes');
    const hostSelect = document.getElementById('host-select');

    for (const agent of agents) {
      const label = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = agent.id;
      label.appendChild(checkbox);
      label.append(` ${agent.name}`);
      checkboxContainer.appendChild(label);
      checkboxContainer.appendChild(document.createElement('br'));

      if (agent.is_host) {
        const option = document.createElement('option');
        option.value = agent.id;
        option.textContent = agent.name;
        hostSelect.appendChild(option);
      }
    }
  })
  .catch(error => {
    document.getElementById('create-error').textContent = 'Error loading agents: ' + error;
  });


document.getElementById('create-form').addEventListener('submit', event => {
  event.preventDefault();

  const title =document.getElementById('title-input').value;
  const topic = document.getElementById('topic-input').value;
  const targetMinutes = Number(document.getElementById('minutes-input').value);
  const hostAgentId = Number(document.getElementById('host-select').value);
  const intros = document.getElementById('intros-input').checked;
  const instructions = document.getElementById('instructions-input').value;

  const checkedBoxes = document.querySelectorAll('#agent-checkboxes input[type="checkbox"]:checked');
  const agentIds = Array.from(checkedBoxes).map(checkbox => Number(checkbox.value));

  const errorBox = document.getElementById('create-error');
  const statusBox = document.getElementById('create-status');
  errorBox.textContent = '';
  statusBox.textContent = '';

  if (agentIds.length < 2) {
    errorBox.textContent = 'Pick at least two agents.';
    return;
  }
  if (!agentIds.includes(hostAgentId)) {
    errorBox.textContent = 'The host must be one of the selected agents.';
    return;
  }

  fetch('http://localhost:8000/episodes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: title,
      topic: topic,
      target_minutes: targetMinutes,
      agent_ids: agentIds,
      intros: intros,
      host_agent_id: hostAgentId,
      instructions: instructions,
    }),
  })
    .then(response => response.json())
    .then(data => {
      statusBox.textContent = `Episode #${data.id} created - status: ${data.status}`;
    })
    .catch(error => {
      errorBox.textContent = 'Error creating episode: ' + error;
    });
});