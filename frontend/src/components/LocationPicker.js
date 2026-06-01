import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, useMap, useMapEvents, CircleMarker, Circle, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { X, LocateFixed, MessageCircle, Send, UserPlus } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './LocationPicker.css';

// Default center (Bangalore as a placeholder like Zepto's origin)
const DEFAULT_CENTER = [12.9716, 77.5946];

const WORLD_BOUNDS = [
  [-85, -180],
  [85, 180],
];

function SingleWorldMap() {
  const map = useMap();

  useEffect(() => {
    map.setMaxBounds(WORLD_BOUNDS);
    map.setMinZoom(2);
    map.setMaxZoom(18);
    map.options.maxBoundsViscosity = 1.0;
    map.options.worldCopyJump = false;
  }, [map]);

  return null;
}

function MapController({ setCenter, setIsDragging }) {
  const map = useMapEvents({
    move: () => {
      const { lat, lng } = map.getCenter();
      setCenter([lat, lng]);
    },
    dragstart: () => setIsDragging(true),
    dragend: () => setIsDragging(true), // Slightly delay to show "jumping" effect
    moveend: () => setIsDragging(false),
  });
  return null;
}

const LocationPicker = ({ token, mode = 'currency', onBack, embedded = false }) => {
  const isPeopleMode = mode === 'people';
  const chatModule = isPeopleMode ? 'people' : 'currency';
  const [center, setCenter] = useState(DEFAULT_CENTER);
  const [, setIsDragging] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null); // To show profile modal
  const [currencyOptions, setCurrencyOptions] = useState(["INR", "EUR", "USD", "GBP"]);
  const [fromCurrency, setFromCurrency] = useState("INR");
  const [toCurrency, setToCurrency] = useState("EUR");
  const [matchingUsers, setMatchingUsers] = useState([]);
  const [rangeKm, setRangeKm] = useState(10);
  const [matchMessage, setMatchMessage] = useState(
    isPeopleMode ? 'Set range and search for live people nearby.' : 'Select currencies and click search.'
  );
  const [socketStatus, setSocketStatus] = useState("connecting");
  const mapRef = useRef();
  const wsRef = useRef(null);
  const chatOpenRef = useRef(false);
  const chatUserRef = useRef(null);

  const [userLivePos, setUserLivePos] = useState(null);
  const [inboxOpen, setInboxOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatUser, setChatUser] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatDraft, setChatDraft] = useState("");
  const [conversations, setConversations] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [requestsOpen, setRequestsOpen] = useState(false);
  const [incomingRequests, setIncomingRequests] = useState([]);
  const [outgoingRequests, setOutgoingRequests] = useState([]);
  const [requestNotice, setRequestNotice] = useState('');

  useEffect(() => {
    chatOpenRef.current = chatOpen;
  }, [chatOpen]);

  useEffect(() => {
    chatUserRef.current = chatUser;
  }, [chatUser]);

  // Auto-detect user current location on mount
  useEffect(() => {
    handleLocateMe();
  }, []);

  useEffect(() => {
    if (isPeopleMode) {
      return;
    }

    const loadCurrencies = async () => {
      try {
        const response = await fetch('https://open.er-api.com/v6/latest/USD');
        const data = await response.json();
        if (data?.rates) {
          const codes = Object.keys(data.rates).sort();
          setCurrencyOptions(codes);
          if (!codes.includes(fromCurrency)) {
            setFromCurrency(codes[0] || "INR");
          }
          if (!codes.includes(toCurrency)) {
            setToCurrency(codes[1] || codes[0] || "EUR");
          }
        }
      } catch (error) {
        console.error("Currency API error:", error);
      }
    };

    loadCurrencies();
  }, [fromCurrency, toCurrency, isPeopleMode]);

  const apiBase = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

const refreshPeopleRequests = useCallback(async () => {
    if (!token || !isPeopleMode) {
      return;
    }
    try {
      const response = await fetch(`${apiBase}/people/requests`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      setIncomingRequests(data.incoming || []);
      setOutgoingRequests(data.outgoing || []);
    } catch (error) {
      console.error('Failed to load requests:', error);
    }
  }, [token, isPeopleMode, apiBase]);

  const refreshConversations = useCallback(async () => {
    if (!token) {
      return;
    }
    try {
      const response = await fetch(`${apiBase}/chat/${chatModule}/conversations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      const conversationList = data.conversations || [];
      setConversations(conversationList);
      setUnreadCount(conversationList.reduce((sum, item) => sum + (item.unread_count || 0), 0));
    } catch (error) {
      console.error("Failed to load conversations:", error);
    }
  }, [token, chatModule, apiBase]);

  const openChat = async (user) => {
    if (!user?.email || !token) {
      return;
    }
    try {
      const response = await fetch(
        `${apiBase}/chat/${chatModule}/messages/${encodeURIComponent(user.email)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      setChatUser(data.partner || user);
      setChatMessages(data.messages || []);
      setChatOpen(true);
      setInboxOpen(false);
      refreshConversations();
    } catch (error) {
      console.error("Failed to open chat:", error);
    }
  };

  const patchUserConnection = (email, patch) => {
    const normalized = email?.toLowerCase();
    if (!normalized) {
      return;
    }
    setMatchingUsers((prev) =>
      prev.map((u) => (u.email?.toLowerCase() === normalized ? { ...u, ...patch } : u))
    );
    setSelectedUser((prev) =>
      prev?.email?.toLowerCase() === normalized ? { ...prev, ...patch } : prev
    );
  };

  useEffect(() => {
    if (!token) {
      return undefined;
    }

    const wsUrl = apiBase.replace(/^http/, 'ws');
    const socket = new WebSocket(`${wsUrl}/ws/match?token=${encodeURIComponent(token)}`);
    wsRef.current = socket;

    socket.onopen = () => setSocketStatus("connected");
    socket.onclose = () => setSocketStatus("disconnected");
    socket.onerror = () => setSocketStatus("error");
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "matches") {
          setMatchingUsers(payload.matches || []);
          const oppositePair = payload.for
            ? `${payload.for.toCurrency} -> ${payload.for.fromCurrency}`
            : "opposite pair";
          const count = (payload.matches || []).length;
          setMatchMessage(
            count > 0
              ? `${count} users found for ${oppositePair}.`
              : `No users found for ${oppositePair}.`
          );
        }
        if (payload.type === "people_matches") {
          setMatchingUsers(payload.matches || []);
          const count = (payload.matches || []).length;
          const range = payload.rangeKm ?? rangeKm;
          setMatchMessage(
            count > 0
              ? `${count} live ${count === 1 ? 'person' : 'people'} within ${range} km.`
              : `No live people within ${range} km right now.`
          );
        }
        if (payload.type === "error") {
          setMatchMessage(payload.message || "Search failed.");
        }
        if (payload.type === "connection_request") {
          refreshPeopleRequests();
          setRequestNotice(
            `${payload.request?.from?.name || 'Someone'} sent you a connection request.`
          );
        }
        if (payload.type === "connection_accepted") {
          refreshPeopleRequests();
          refreshConversations();
          const withUser = payload.connection?.with;
          if (withUser?.email) {
            patchUserConnection(withUser.email, {
              connectionStatus: 'accepted',
              name: withUser.name,
              avatar: withUser.avatar,
            });
          }
          setRequestNotice(
            `${withUser?.name || 'Someone'} accepted your request. Open Messages to chat.`
          );
        }
        if (payload.type === "connection_removed") {
          refreshPeopleRequests();
          if (chatUserRef.current?.email === payload.partner) {
            setChatOpen(false);
            setChatUser(null);
            setChatMessages([]);
          }
        }
        if (payload.type === "new_message") {
          if (payload.module && payload.module !== chatModule) {
            return;
          }
          const incoming = payload.message;
          const isCurrentOpenChat =
            chatOpenRef.current && chatUserRef.current?.email === incoming.sender;

          if (isCurrentOpenChat) {
            setChatMessages((prev) => [...prev, incoming]);
            refreshConversations();
            return;
          }

          setConversations((prev) => {
            const others = prev.filter((entry) => entry.partner?.email !== incoming.sender);
            const senderName = incoming.sender.split("@", 1)[0];
            return [
              {
                partner: {
                  email: incoming.sender,
                  name: senderName,
                  avatar: senderName.slice(0, 2).toUpperCase(),
                  online: true,
                },
                last_message: incoming,
                unread_count: 1,
              },
              ...others,
            ];
          });
          setUnreadCount((prev) => prev + 1);
        }
        if (payload.type === "message_sent") {
          if (payload.module && payload.module !== chatModule) {
            return;
          }
          const outgoing = payload.message;
          if (chatOpenRef.current && chatUserRef.current?.email === outgoing.recipient) {
            setChatMessages((prev) => [...prev, outgoing]);
          }
          refreshConversations();
        }
      } catch (error) {
        setMatchMessage("Invalid response from websocket.");
      }
    };

    return () => {
      socket.close();
    };
  }, [rangeKm, refreshConversations, refreshPeopleRequests]);

  useEffect(() => {
    refreshConversations();
    refreshPeopleRequests();
  }, [token, chatModule,refreshConversations, refreshPeopleRequests]);

  const handleLocateMe = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          const pos = [latitude, longitude];
          setCenter(pos);
          setUserLivePos(pos);
          if (mapRef.current) {
            mapRef.current.setView(pos, 18);
          }
        },
        (error) => {
          console.error("Geolocation error:", error);
        }
      );
    }
  };

  const getSearchCoords = () => ({
    lat: userLivePos ? userLivePos[0] : center[0],
    lng: userLivePos ? userLivePos[1] : center[1],
  });

  const handleCurrencySearch = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setMatchMessage("WebSocket not connected yet.");
      return;
    }
    const coords = getSearchCoords();
    wsRef.current.send(
      JSON.stringify({
        type: "search",
        fromCurrency,
        toCurrency,
        lat: coords.lat,
        lng: coords.lng,
      })
    );
    setMatchMessage("Searching opposite currency users...");
  };

  const handlePeopleSearch = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setMatchMessage("WebSocket not connected yet.");
      return;
    }
    const coords = getSearchCoords();
    wsRef.current.send(
      JSON.stringify({
        type: "search_people",
        lat: coords.lat,
        lng: coords.lng,
        rangeKm,
      })
    );
    setMatchMessage(`Searching live people within ${rangeKm} km...`);
  };

  const handleSendMessage = () => {
    const text = chatDraft.trim();
    if (!text || !chatUser?.email) {
      return;
    }
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setMatchMessage("WebSocket not connected yet.");
      return;
    }
    wsRef.current.send(
      JSON.stringify({
        type: "send_message",
        module: chatModule,
        toEmail: chatUser.email,
        text,
      })
    );
    setChatDraft("");
  };

  const sendPeopleRequest = async (user) => {
    if (!user?.email) {
      return;
    }
    try {
      const response = await fetch(`${apiBase}/people/requests`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ to_email: user.email }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to send request.');
      }
      setRequestNotice(`Request sent to ${user.name}.`);
      const patch = {
        connectionStatus: 'pending_outgoing',
        requestId: data.request?.id,
      };
      patchUserConnection(user.email, patch);
      setSelectedUser({ ...user, ...patch });
      refreshPeopleRequests();
    } catch (error) {
      setMatchMessage(error.message);
    }
  };

  const acceptPeopleRequest = async (requestId, partner = null) => {
    try {
      const response = await fetch(`${apiBase}/people/requests/${requestId}/accept`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to accept request.');
      }
      const chatPartner =
        partner ||
        selectedUser ||
        incomingRequests.find((r) => r.id === requestId)?.from;
      if (chatPartner?.email) {
        patchUserConnection(chatPartner.email, { connectionStatus: 'accepted', requestId: undefined });
        await openChat(chatPartner);
      }
      setRequestNotice('Request accepted. You can chat now.');
      refreshPeopleRequests();
      refreshConversations();
      setRequestsOpen(false);
    } catch (error) {
      setMatchMessage(error.message);
    }
  };

  const cancelPeopleRequest = async (requestId, partnerEmail) => {
    try {
      const response = await fetch(`${apiBase}/people/requests/${requestId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to cancel request.');
      }
      if (partnerEmail) {
        patchUserConnection(partnerEmail, { connectionStatus: 'none', requestId: undefined });
      }
      setRequestNotice('Request cancelled.');
      refreshPeopleRequests();
    } catch (error) {
      setMatchMessage(error.message);
    }
  };

  const rejectPeopleRequest = async (requestId, partnerEmail) => {
    try {
      await fetch(`${apiBase}/people/requests/${requestId}/reject`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (partnerEmail) {
        patchUserConnection(partnerEmail, { connectionStatus: 'none', requestId: undefined });
      }
      refreshPeopleRequests();
    } catch (error) {
      console.error(error);
    }
  };

  const removePeopleConnection = async (partnerEmail) => {
    if (!partnerEmail) {
      return;
    }
    try {
      const response = await fetch(
        `${apiBase}/people/connections/${encodeURIComponent(partnerEmail)}`,
        { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to remove connection.');
      }
      setChatOpen(false);
      setChatUser(null);
      setChatMessages([]);
      setSelectedUser(null);
      setRequestNotice('Connection removed.');
      refreshPeopleRequests();
      refreshConversations();
    } catch (error) {
      setMatchMessage(error.message);
    }
  };

  const incomingRequestCount = incomingRequests.length;

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className={`location-picker-container${embedded ? ' embedded' : ''}`}
    >
      <div className="currency-toolbar">
        {isPeopleMode ? (
          <div className="currency-toolbar-row people-toolbar-row">
            <label className="range-label" htmlFor="search-range">
              Range: <strong>{rangeKm} km</strong>
            </label>
            <input
              id="search-range"
              type="range"
              min="1"
              max="50"
              step="1"
              value={rangeKm}
              onChange={(e) => setRangeKm(Number(e.target.value))}
            />
            <button type="button" onClick={handlePeopleSearch}>
              Find live people
            </button>
          </div>
        ) : (
          <div className="currency-toolbar-row">
            <select value={fromCurrency} onChange={(e) => setFromCurrency(e.target.value)}>
              {currencyOptions.map((currency) => (
                <option key={`from-${currency}`} value={currency}>
                  {currency}
                </option>
              ))}
            </select>
            <span className="currency-arrow">to</span>
            <select value={toCurrency} onChange={(e) => setToCurrency(e.target.value)}>
              {currencyOptions.map((currency) => (
                <option key={`to-${currency}`} value={currency}>
                  {currency}
                </option>
              ))}
            </select>
            <button type="button" onClick={handleCurrencySearch}>
              Search
            </button>
          </div>
        )}
        <div className="currency-match-text">
          {requestNotice || matchMessage}{' '}
          <span className={`ws-status ws-${socketStatus}`}></span>
        </div>
      </div>

      <div className="map-wrapper map-only-view">
        <MapContainer
          center={DEFAULT_CENTER}
          zoom={16}
          minZoom={2}
          maxZoom={18}
          maxBounds={WORLD_BOUNDS}
          maxBoundsViscosity={1.0}
          worldCopyJump={false}
          scrollWheelZoom="center"
          doubleClickZoom="center"
          style={{ height: '100%', width: '100%' }}
          zoomControl={false}
          ref={mapRef}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            noWrap
          />
          <SingleWorldMap />
          <MapController setCenter={setCenter} setIsDragging={setIsDragging} />

          {/* Render Other Users as Red Dots */}
          {matchingUsers.map((user) => (
            <CircleMarker
              key={user.id}
              center={[user.lat, user.lng]}
              radius={8}
              pathOptions={{
                fillColor: isPeopleMode ? '#2563eb' : '#ff3269',
                color: 'white',
                weight: 2,
                fillOpacity: 0.9,
              }}
              eventHandlers={{
                click: () => setSelectedUser(user)
              }}
            >
              <Tooltip direction="top" offset={[0, -10]} opacity={1}>
                <div className="map-marker-tooltip">
                  <strong>{user.name}</strong>
                  {isPeopleMode && user.connectionStatus === 'pending_outgoing' && (
                    <span className="map-tooltip-hint">Request sent · tap marker to cancel</span>
                  )}
                  {isPeopleMode && user.connectionStatus === 'pending_incoming' && (
                    <span className="map-tooltip-hint">Wants to connect · tap to respond</span>
                  )}
                  {isPeopleMode && user.connectionStatus === 'accepted' && (
                    <span className="map-tooltip-hint">Connected · tap to chat</span>
                  )}
                </div>
              </Tooltip>
            </CircleMarker>
          ))}

          {isPeopleMode && userLivePos && (
            <Circle
              center={userLivePos}
              radius={rangeKm * 1000}
              pathOptions={{
                color: '#3498db',
                fillColor: '#3498db',
                fillOpacity: 0.08,
                weight: 1,
              }}
            />
          )}

          {/* User's Own Live Location (Blue Pulse Dot) */}
          {userLivePos && (
             <CircleMarker 
               center={userLivePos}
               radius={10}
               pathOptions={{ 
                 fillColor: '#3498db', 
                 color: 'white', 
                 weight: 3, 
                 fillOpacity: 1 
               }}
             >
                <Tooltip direction="top" offset={[0, -12]} opacity={1}>
                   You are here
                </Tooltip>
             </CircleMarker>
          )}
        </MapContainer>

        <button className="locate-me-btn bottom-20" onClick={handleLocateMe}>
          <LocateFixed size={24} color={isPeopleMode ? '#2563eb' : '#ff3269'} />
        </button>

        {isPeopleMode && (
          <button
            className="requests-btn"
            onClick={() => {
              refreshPeopleRequests();
              setRequestsOpen(true);
            }}
            title="Connection requests"
          >
            <UserPlus size={22} color="#2563eb" />
            {incomingRequestCount > 0 && (
              <span className="messages-badge">{incomingRequestCount}</span>
            )}
          </button>
        )}

        <button className="messages-btn" onClick={() => setInboxOpen(true)}>
          <MessageCircle size={22} color={isPeopleMode ? '#2563eb' : '#ff3269'} />
          {unreadCount > 0 && <span className="messages-badge">{unreadCount}</span>}
        </button>

        {/* Profile Pop-up Modal */}
        <AnimatePresence>
          {selectedUser && (
            <motion.div 
              className="user-profile-modal"
              initial={{ opacity: 0, y: 50, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 50, scale: 0.9 }}
            >
              <div className="profile-close" onClick={() => setSelectedUser(null)}>
                 <X size={20} />
              </div>
              <div className="profile-header">
                 <div className="profile-avatar">{selectedUser.avatar}</div>
                 <div className="profile-info">
                   <div className="profile-name">{selectedUser.name}</div>
                   <div className="profile-status">
                     {isPeopleMode
                       ? `${selectedUser.distanceKm ?? '?'} km away · Live now`
                       : `${selectedUser.fromCurrency} to ${selectedUser.toCurrency}`}
                   </div>
                 </div>
              </div>
              <div className="profile-bio">
                {isPeopleMode
                  ? selectedUser.bio || 'Nearby and available to chat.'
                  : selectedUser.bio}
              </div>
              {!isPeopleMode && (
                <button className="profile-action-btn" onClick={() => openChat(selectedUser)}>
                  Message {selectedUser.name.split(' ')[0]}
                </button>
              )}
              {isPeopleMode && selectedUser.connectionStatus === 'accepted' && (
                <>
                  <button className="profile-action-btn" onClick={() => openChat(selectedUser)}>
                    Message {selectedUser.name.split(' ')[0]}
                  </button>
                  <button
                    type="button"
                    className="profile-secondary-btn"
                    onClick={() => removePeopleConnection(selectedUser.email)}
                  >
                    Remove connection
                  </button>
                </>
              )}
              {isPeopleMode && selectedUser.connectionStatus === 'pending_outgoing' && (
                <button
                  type="button"
                  className="profile-secondary-btn profile-cancel-btn"
                  onClick={() =>
                    cancelPeopleRequest(selectedUser.requestId, selectedUser.email)
                  }
                >
                  Cancel request
                </button>
              )}
              {isPeopleMode && selectedUser.connectionStatus === 'pending_incoming' && (
                <>
                  <button
                    type="button"
                    className="profile-action-btn"
                    onClick={() => acceptPeopleRequest(selectedUser.requestId, selectedUser)}
                  >
                    Accept request
                  </button>
                  <button
                    type="button"
                    className="profile-secondary-btn"
                    onClick={() =>
                      rejectPeopleRequest(selectedUser.requestId, selectedUser.email)
                    }
                  >
                    Decline
                  </button>
                </>
              )}
              {isPeopleMode &&
                (!selectedUser.connectionStatus || selectedUser.connectionStatus === 'none') && (
                  <button
                    type="button"
                    className="profile-action-btn"
                    onClick={() => sendPeopleRequest(selectedUser)}
                  >
                    Send request
                  </button>
                )}
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {requestsOpen && isPeopleMode && (
            <motion.div
              className="inbox-modal requests-modal"
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 30 }}
            >
              <div className="inbox-header">
                <h3>Connection requests</h3>
                <button type="button" onClick={() => setRequestsOpen(false)}>
                  <X size={18} />
                </button>
              </div>
              <div className="requests-section-title">Incoming</div>
              <div className="inbox-list">
                {incomingRequests.length === 0 ? (
                  <div className="empty-inbox">No incoming requests.</div>
                ) : (
                  incomingRequests.map((item) => (
                    <div key={item.id} className="request-item">
                      <div>
                        <div className="inbox-item-name">{item.from.name}</div>
                        <div className="inbox-item-text">{item.from.email}</div>
                      </div>
                      <div className="request-actions">
                        <button type="button" onClick={() => acceptPeopleRequest(item.id, item.from)}>
                          Accept
                        </button>
                        <button type="button" onClick={() => rejectPeopleRequest(item.id)}>
                          Decline
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
              <div className="requests-section-title">Sent</div>
              <div className="inbox-list">
                {outgoingRequests.length === 0 ? (
                  <div className="empty-inbox">No sent requests.</div>
                ) : (
                  outgoingRequests.map((item) => (
                    <div key={item.id} className="request-item pending-only">
                      <div>
                        <div className="inbox-item-name">{item.to.name}</div>
                        <div className="inbox-item-text">Waiting for response</div>
                      </div>
                      <button
                        type="button"
                        className="request-cancel-link"
                        onClick={() => cancelPeopleRequest(item.id, item.to.email)}
                      >
                        Cancel
                      </button>
                    </div>
                  ))
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {inboxOpen && (
            <motion.div
              className="inbox-modal"
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 30 }}
            >
              <div className="inbox-header">
                <h3>{isPeopleMode ? 'People Finder chats' : 'Currency Exchange chats'}</h3>
                <button type="button" onClick={() => setInboxOpen(false)}>
                  <X size={18} />
                </button>
              </div>
              <div className="inbox-list">
                {conversations.length === 0 ? (
                  <div className="empty-inbox">No messages yet.</div>
                ) : (
                  conversations.map((conversation) => (
                    <button
                      key={conversation.partner.email}
                      type="button"
                      className="inbox-item"
                      onClick={() => openChat(conversation.partner)}
                    >
                      <div className="inbox-item-name">{conversation.partner.name}</div>
                      <div className="inbox-item-text">
                        {conversation.last_message?.text ||
                          (isPeopleMode ? 'Connected · say hi' : 'Start chatting')}
                      </div>
                      {(conversation.unread_count || 0) > 0 && (
                        <span className="inbox-item-badge">{conversation.unread_count}</span>
                      )}
                    </button>
                  ))
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {chatOpen && chatUser && (
            <motion.div
              className="chat-modal"
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 30 }}
            >
              <div className="chat-header">
                <div>
                  <div className="chat-title">{chatUser.name}</div>
                  <div className="chat-subtitle">{chatUser.email}</div>
                </div>
                <div className="chat-header-actions">
                  {isPeopleMode && (
                    <button
                      type="button"
                      className="chat-remove-btn"
                      onClick={() => removePeopleConnection(chatUser.email)}
                    >
                      Remove
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      setChatOpen(false);
                      setChatUser(null);
                      setChatMessages([]);
                      setChatDraft("");
                    }}
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>

              <div className="chat-body">
                {chatMessages.length === 0 ? (
                  <div className="empty-inbox">No messages yet. Say hi.</div>
                ) : (
                  chatMessages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`chat-bubble ${msg.sender === chatUser.email ? "incoming" : "outgoing"}`}
                    >
                      {msg.text}
                    </div>
                  ))
                )}
              </div>

              <div className="chat-input-row">
                <input
                  type="text"
                  placeholder={`Message ${chatUser.name}`}
                  value={chatDraft}
                  onChange={(e) => setChatDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleSendMessage();
                    }
                  }}
                />
                <button type="button" onClick={handleSendMessage}>
                  <Send size={16} />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};

export default LocationPicker;
