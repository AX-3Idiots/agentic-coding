import React from "react"
import { BrowserRouter as Router } from "react-router-dom"
import { Provider } from "react-redux"
import { store } from "./store/store"

function App() {
  return (
    <Provider store={store}>
      <Router>
        <div className="App">
          <h1>User Authentication System</h1>
          {/* Routes will be added here */}
        </div>
      </Router>
    </Provider>
  )
}

export default App
