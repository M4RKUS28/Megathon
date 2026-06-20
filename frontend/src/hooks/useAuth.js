import { useEffect, useState } from "react";
import { getUserInfo, initKeycloak, isAuthenticated, login, logout, register } from "@/lib/auth";
export function useAuth() {
    const [state, setState] = useState({
        ready: false,
        authenticated: false,
        user: null,
    });
    useEffect(() => {
        initKeycloak()
            .then(() => {
            setState({
                ready: true,
                authenticated: isAuthenticated(),
                user: getUserInfo(),
            });
        })
            .catch((err) => {
            // Don't hang on the loading screen if Keycloak init fails
            // (unreachable server, missing realm, etc.) — fall through as
            // unauthenticated so the user lands on the login page.
            console.error("Keycloak init failed:", err);
            setState({ ready: true, authenticated: false, user: null });
        });
    }, []);
    return { ...state, login, logout, register };
}
