export default function RelatedTopics({ topics, onSearch }) {
  if (!topics?.length) return null;
  return (
    <div>
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
        🔗 Related Topics
      </p>
      <div className="flex flex-wrap gap-2">
        {topics.map((topic) => (
          <button
            key={topic}
            onClick={() => onSearch(topic)}
            className="bg-indigo-950/60 hover:bg-indigo-900/60 border border-indigo-800/50
                       text-indigo-300 text-xs px-3 py-1.5 rounded-full transition-colors"
          >
            {topic}
          </button>
        ))}
      </div>
    </div>
  );
}
