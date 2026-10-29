
import { initializeApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider
} from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyDFiXFkmfulLdfpKSwrizljaAlnrhF8xpU",
  authDomain: "taskflow-app-e6571.firebaseapp.com",
  projectId: "taskflow-app-e6571",
  storageBucket: "taskflow-app-e6571.firebasestorage.app",
  messagingSenderId: "663880178047",
  appId: "1:663880178047:web:f20040aa20f2893ca6624a"
};

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);

export const googleProvider = new GoogleAuthProvider();
