import React, { createContext, useContext, ReactNode } from 'react';
import { getLanguage, setLanguage, t, getDirection, formatDate, formatNumber } from './i18n';

const TranslationContext = createContext({
  language: 'en',
  direction: 'ltr',
  setLanguage: () => {},
  t: (key) => key,
  formatDate: (date) => date.toString(),
  formatNumber: (num) => num.toString(),
});

export function useTranslation() {
  return useContext(TranslationContext);
}

export function TranslationProvider({ children }) {
  const [language, setLanguageState] = React.useState(getLanguage());
  const [updateKey, setUpdateKey] = React.useState(0);
  const direction = getDirection(language);

  // Update when language changes (from localStorage)
  React.useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === 'taskloom.language') {
        const newLang = e.newValue || 'en';
        setLanguageState(newLang);
        setUpdateKey(k => k + 1);
      }
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const contextValue = {
    language,
    direction,
    setLanguage: (lang) => {
      setLanguageState(lang);
      setLanguage(lang);
      setUpdateKey(k => k + 1);
      // Trigger storage event for other tabs
      window.dispatchEvent(new StorageEvent('storage', {
        key: 'taskloom.language',
        newValue: lang,
        storageArea: localStorage
      }));
    },
    t: (key) => t(key, language),
    formatDate: (date) => formatDate(date, language),
    formatNumber: (num) => formatNumber(num, language),
  };

  return (
    <TranslationContext.Provider value={contextValue} key={updateKey}>
      {children}
    </TranslationContext.Provider>
  );
}

// Helper hook for components that need translation
export function useT() {
  const { t } = useTranslation();
  return t;
}