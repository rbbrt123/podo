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