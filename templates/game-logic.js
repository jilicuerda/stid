class VolleyMatch {
    constructor() {
        this.resetState();
    }

    resetState() {
        this.state = {
            home: { name: "Home", score: 0, sets: 0, players: [], onCourt: [] },
            away: { name: "Away", score: 0, sets: 0, players: [], onCourt: [] },
            server: null, // 'home' or 'away'
            set: 1,
            history: [],
            // Temporary storage for the modal selection
            tempPoint: { winner: null, actorTeam: null, actorNum: null },
            subTarget: { team: null, idx: null }
        };
    }

    /**
     * Initializes a new match with the data from the Setup Wizard
     */
    initializeMatch(homeName, awayName, firstServer, homeRoster, homeCourt, awayRoster, awayCourt) {
        this.state.home.name = homeName;
        this.state.home.players = homeRoster;
        this.state.home.onCourt = homeCourt;

        this.state.away.name = awayName;
        this.state.away.players = awayRoster;
        this.state.away.onCourt = awayCourt;

        this.state.server = firstServer;
        this.state.set = 1;
        this.state.home.score = 0;
        this.state.away.score = 0;
        this.state.history = [];
    }

    /**
     * CORE ENGINE: Handles Scoring + Rotation + History
     */
    scorePoint(winner, details) {
        // 1. Capture Context BEFORE updating scores (for history)
        const currentServerTeam = this.state.server;
        const currentServerNum = this.state[currentServerTeam].onCourt[0].num; // Pos 1 is index 0
        
        // Save Rotations as strings (e.g., "4-2-8-10-12-1")
        const rotHome = this.state.home.onCourt.map(p => p.num).join('-');
        const rotAway = this.state.away.onCourt.map(p => p.num).join('-');

        // 2. Increment Score
        this.state[winner].score++;

        // 3. Log to History
        const logEntry = {
            set: this.state.set,
            score_dom: this.state.home.score,
            score_ext: this.state.away.score,
            winner_team: this.state[winner].name,
            point_type: (details.actorTeam === winner) ? 'Won' : 'Opp Error', // Simple logic
            action: details.action || 'Unknown',
            actor_num: details.actorNum || '?',
            actor_team: details.actorTeam ? this.state[details.actorTeam].name : '?',
            server_team: this.state[currentServerTeam].name,
            server_num: currentServerNum,
            rot_home: rotHome,
            rot_away: rotAway,
            timestamp: new Date().toISOString()
        };
        this.state.history.push(logEntry);

        // 4. Rotation Logic (Side-out)
        // If the winner was NOT the server, they get the ball and rotate.
        if (this.state.server !== winner) {
            this.rotate(winner);
            this.state.server = winner;
        }
    }

    /**
     * Standard Indoor Volleyball Rotation
     * Array Index 0 is Position 1 (Server).
     * Array Index 1 is Position 2...
     * Rotation moves players: P2->P1, P3->P2, etc.
     * In Array terms: We shift the first element out and push it to the back?
     * NO. 
     * Visual Rotation is Clockwise.
     * P1(idx0) moves to P6(idx5).
     * P2(idx1) moves to P1(idx0).
     * So, we take the player at index 0, and move them to the end? No.
     * We remove the first element (Pos 1) and put them at the end? 
     * Let's trace: [P1, P2, P3, P4, P5, P6]
     * New P1 should be old P2.
     * So yes: Array Shift (Remove P1), Array Push (Add P1 to end).
     */
    rotate(team) {
        const squad = this.state[team].onCourt;
        const server = squad.shift(); // Remove player at index 0 (Pos 1)
        squad.push(server); // Add them to end (Pos 6)
        // Wait, Pos 6 in array logic is index 5.
        // If we want P2 to become P1:
        // [1, 2, 3, 4, 5, 6] -> shift -> 1 is gone. [2, 3, 4, 5, 6].
        // push 1 -> [2, 3, 4, 5, 6, 1].
        // Now index 0 is 2. (P2 became P1). Correct.
    }

    /**
     * Substitution Logic
     */
    substitute(team, courtIndex, newPlayerNum) {
        // Find the player object in the full roster
        const newPlayer = this.state[team].players.find(p => p.num == newPlayerNum);
        if (newPlayer) {
            this.state[team].onCourt[courtIndex] = newPlayer;
        }
    }

    /**
     * End of Set Logic
     */
    endSet() {
        // Determine winner of set
        if (this.state.home.score > this.state.away.score) {
            this.state.home.sets++;
        } else {
            this.state.away.sets++;
        }

        // Logic for next set (Reset scores, increment set count)
        this.state.set++;
        this.state.home.score = 0;
        this.state.away.score = 0;
        
        // Note: We do NOT reset rotation automatically. 
        // In real volley, you might submit a new lineup, but usually, 
        // apps keep the last rotation or ask for a new one. 
        // We keep current rotation for simplicity unless user reloads.
        
        return true; // Return true to signal UI to update
    }

    /**
     * Backup Generator
     */
    generateBackupJSON() {
        return "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(this.state));
    }

    /**
     * Load Backup
     */
    loadFromJSON(jsonString) {
        try {
            const data = JSON.parse(jsonString);
            // Basic validation
            if (data.home && data.away && data.history) {
                this.state = data;
                return true;
            }
            return false;
        } catch (e) {
            console.error("Invalid JSON", e);
            return false;
        }
    }
}
