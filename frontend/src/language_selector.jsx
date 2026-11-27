import React from 'react';
import { Globe, ChevronDown, ChevronUp } from 'lucide-react';
import { getLanguage, setLanguage, getAvailableLanguages, t } from './i18n';
import { useTranslation } from './translation_context';

export function LanguageSelector({ className = '' }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const { language: currentLang, setLanguage } = useTranslation();
  const languages = getAvailableLanguages();
  
  const currentLanguage = languages.find(l => l.code === currentLang) || languages[0];

  function handleLanguageChange(langCode) {
    setLanguage(langCode);
    setIsOpen(false);
    // Force reload after language change
    setTimeout(() => window.location.reload(), 100);
  }

  return (
    <div className={`language-selector-wrapper ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="language-selector-btn"
        aria-label={t("language", currentLang)}
      >
        <Globe size={16} />
        <span className="language-selector-current">{currentLanguage.code.toUpperCase()}</span>
        {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      
      {isOpen && (
        <>
          <div className="language-selector-backdrop" onClick={() => setIsOpen(false)} />
          <div className="language-selector-dropdown">
            {languages.map((lang) => (
              <button
                key={lang.code}
                type="button"
                onClick={() => handleLanguageChange(lang.code)}
                className={`language-selector-option ${currentLang === lang.code ? 'active' : ''}`}
              >
                <span className="language-code">{lang.code.toUpperCase()}</span>
                <span className="language-name">{lang.name}</span>
                {currentLang === lang.code && <span className="language-check">✓</span>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default LanguageSelector;