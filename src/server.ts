import http from 'http';
import { Server } from 'socket.io';
import app from './app'; // Import the Express app

const PORT = process.env.PORT || 3000;
const server = http.createServer(app);

const io = new Server(server, {
    cors: { origin: '*' },
});

io.on('connection', (socket) => {
    console.log('A user connected:', socket.id);

    // Example: Handle messages
    socket.on('message', (data) => {
        console.log('Message received:', data);
        socket.emit('message', `Server received: ${data}`);
    });

    socket.on('disconnect', () => {
        console.log('A user disconnected:', socket.id);
    });
});

server.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});
