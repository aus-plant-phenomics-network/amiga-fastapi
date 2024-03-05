import TopicMonitor from './TopicMonitor';

function App() {
    return (
        <div className="App">
            <a href={"/simple_lidar"}>LIDAR</a>
            <header className="App-header">
                <h1>Farm-ng Monitor</h1>
                <TopicMonitor />
            </header>
        </div>
    );
}

export default App;
