// Send a simple message
const response = await client.send({
  type: 'greeting',
  payload: { message: 'Hello, MPAC!' }
});

console.log('Server response:', response);