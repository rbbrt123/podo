fetch('http://localhost:8000/episodes')
  .then(response => response.json())
  .then(data => {
    document.getElementById('output').textContent = JSON.stringify(data, null, 2);
  })
  .catch(error => {
    document.getElementById('output').textContent = 'Error: ' + error;
  });