const BACKEND_URL = 'http://localhost:8000';

document.querySelectorAll('.tab-button').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

    button.classList.add('active');
    document.getElementById(`tab-${button.dataset.tab}`).classList.add('active');
  });
});


fetch(`${BACKEND_URL}/episodes`)
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

  
fetch(`${BACKEND_URL}/agents`)
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


let pollTimer = null;

function pollEpisode(episodeId) {
  fetch(`${BACKEND_URL}/episodes/${episodeId}`)
    .then(response => response.json())
    .then(episode => {
      const statusBox = document.getElementById('create-status');
      const audio = document.getElementById('episode-audio');
      const transcriptBox = document.getElementById('episode-transcript');
      const elapsedMin = episode.elapsed_seconds / 60;

      if (episode.status === 'complete') {
        clearInterval(pollTimer);
        pollTimer = null;
        let statusText = `Episode #${episodeId}: done! (${elapsedMin.toFixed(1)} min)`;
        if (episode.error_message) {
            statusText = `Episode #${episodeId}: done, but short — ${elapsedMin.toFixed(1)}/${episode.target_minutes} min. ${episode.error_message}`;
          }
        statusBox.textContent = statusText;
        audio.src = `${BACKEND_URL}/episodes/${episodeId}/audio`;
        audio.classList.remove('hidden');
        transcriptBox.value = episode.turns.map(t => `${t.speaker}: ${t.text}`).join('\n\n');
        transcriptBox.classList.remove('hidden');
      } else if (episode.status === 'failed') {
        clearInterval(pollTimer);
        pollTimer = null;
        statusBox.textContent = `Episode #${episodeId} failed: ${episode.error_message}`;
      } else {
        statusBox.textContent = `Episode #${episodeId}: ${episode.status}... (${elapsedMin.toFixed(1)}/${episode.target_minutes} min)`;
      }
    })
    .catch(error => {
      document.getElementById('create-error').textContent = 'Error polling episode: ' + error;
    });
}


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
  const audio = document.getElementById('episode-audio');
  const transcriptBox = document.getElementById('episode-transcript');

  errorBox.textContent = '';
  statusBox.textContent = '';
  audio.classList.add('hidden');
  audio.removeAttribute('src');
  transcriptBox.classList.add('hidden');
  transcriptBox.value = '';

  if (agentIds.length < 2) {
    errorBox.textContent = 'Pick at least two agents.';
    return;
  }
  if (!agentIds.includes(hostAgentId)) {
    errorBox.textContent = 'The host must be one of the selected agents.';
    return;
  }

  fetch(`${BACKEND_URL}/episodes`, {
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
      statusBox.textContent = `Episode #${data.id}: pending...`;

      if (pollTimer) {
        clearInterval(pollTimer);
      }
      pollTimer = setInterval(() => pollEpisode(data.id), 2000);
    })
    .catch(error => {
      errorBox.textContent = 'Error creating episode: ' + error;
    });
});