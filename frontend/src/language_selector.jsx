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
    <div className={`relative ${className}`} dir="ltr">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        aria-label={t("language")}
      >
        <Globe size={16} />
        <span>{currentLanguage.name}</span>
        {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      
      {isOpen && (
        <div className="absolute top-full right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg border border-gray-200 dark:border-gray-700 z-50">
          <div className="py-1">
            {languages.map((lang) => (
              <button
                key={lang.code}
                type="button"
                onClick={() => handleLanguageChange(lang.code)}
                className={`w-full px-4 py-2 text-left text-sm ${
                  currentLang === lang.code
                    ? 'bg-gray-100 dark:bg-gray-700 font-medium'
                    : 'hover:bg-gray-50 dark:hover:bg-gray-700'
                }`}
              >
                {lang.name}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default LanguageSelector;