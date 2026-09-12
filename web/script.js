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
    document.getElementById('create-error').textcontent = 'Error loading agents: ' + error;
  });