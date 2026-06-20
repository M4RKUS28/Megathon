declare const _default: {
    darkMode: ["class"];
    content: string[];
    theme: {
        extend: {
            fontFamily: {
                display: [string, string, string, string];
                sans: [string, string, string, string];
                mono: [string, string, string, string];
            };
            borderRadius: {
                lg: string;
                md: string;
                sm: string;
            };
            colors: {
                ink: string;
                paper: string;
                iris: string;
                signal: string;
                mist: string;
                background: string;
                foreground: string;
                primary: {
                    DEFAULT: string;
                    foreground: string;
                };
                secondary: {
                    DEFAULT: string;
                    foreground: string;
                };
                muted: {
                    DEFAULT: string;
                    foreground: string;
                };
                accent: {
                    DEFAULT: string;
                    foreground: string;
                };
                destructive: {
                    DEFAULT: string;
                    foreground: string;
                };
                border: string;
                card: {
                    DEFAULT: string;
                    foreground: string;
                };
            };
            keyframes: {
                "assemble-in": {
                    "0%": {
                        opacity: string;
                        transform: string;
                    };
                    "100%": {
                        opacity: string;
                        transform: string;
                    };
                };
                drift: {
                    "0%, 100%": {
                        transform: string;
                    };
                    "50%": {
                        transform: string;
                    };
                };
            };
            animation: {
                "assemble-in": string;
                drift: string;
            };
        };
    };
    plugins: any[];
};
export default _default;
